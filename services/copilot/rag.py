"""Document search (RAG) over NetHeal's own docs, for the Ask NetHeal assistant.

Docs are split at "## " headings. Chunks are embedded with BAAI/bge-base-en-v1.5 on the
Cirrascale AI Suite and searched by cosine similarity; without the AI service a simple
keyword overlap is used instead, so search keeps working offline.
"""

import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DOCS = ["README.md", "docs/PRODUCT_OVERVIEW.md", "theory/ML.md", "docs/RESEARCH.md",
        "docs/CONTRACTS.md", "policies/healing.rego"]  # fmt: skip
EMBED_MODEL = "BAAI/bge-base-en-v1.5"
MAX_CHARS = 1500


def chunks() -> list[dict]:
    out = []
    for rel in DOCS:
        path = ROOT / rel
        if not path.exists():
            continue
        for part in re.split(r"\n(?=## )", path.read_text()):
            title = part.strip().splitlines()[0].lstrip("#").strip() if part.strip() else rel
            out.append({"source": f"{rel} · {title}", "text": part.strip()[:MAX_CHARS]})
    return out


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


class DocIndex:
    def __init__(self, client=None):
        self.client, self.docs, self.vectors = client, chunks(), None

    async def _embed(self, texts: list[str]) -> np.ndarray:
        out = []
        for i in range(0, len(texts), 16):
            res = await self.client.embeddings.create(model=EMBED_MODEL, input=texts[i : i + 16])
            out += [d.embedding for d in res.data]
        v = np.array(out, dtype=np.float32)
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    async def search(self, query: str, k: int = 3) -> list[dict]:
        if self.client is not None:
            try:
                if self.vectors is None:
                    self.vectors = await self._embed([d["text"] for d in self.docs])
                scores = self.vectors @ (await self._embed([query]))[0]
                return [self.docs[i] for i in np.argsort(-scores)[:k]]
            except Exception:
                pass  # AI service unreachable: fall back to keywords
        q = _words(query)
        ranked = sorted(self.docs, key=lambda d: len(q & _words(d["text"])), reverse=True)
        return ranked[:k]
