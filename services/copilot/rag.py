"""Document search (RAG) over NetHeal's own docs, for the Ask NetHeal assistant.

Docs are split at "## " headings. Chunks are embedded with BAAI/bge-base-en-v1.5 on the
Cirrascale AI Suite and searched by cosine similarity; without the AI service a simple
keyword overlap is used instead, so search keeps working offline.
"""

import asyncio
import hashlib
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DOCS = ["README.md", "docs/PRODUCT_OVERVIEW.md", "theory/ML.md", "docs/RESEARCH.md",
        "docs/CONTRACTS.md", "docs/EVALUATION.md", "config/healing.rego"]  # fmt: skip
EMBED_MODEL = "BAAI/bge-base-en-v1.5"
MAX_CHARS = 1500


def chunks() -> list[dict]:
    out = []
    for rel in DOCS:
        path = ROOT / rel
        if not path.exists():
            continue
        for part in re.split(r"\n(?=## )", path.read_text(encoding="utf-8")):
            title = part.strip().splitlines()[0].lstrip("#").strip() if part.strip() else rel
            text = part.strip()
            for start in range(0, len(text), MAX_CHARS - 200):
                out.append(
                    {
                        "source": (
                            f"{rel} · {title} · chars "
                            f"{start + 1}-{min(start + MAX_CHARS, len(text))}"
                        ),
                        "text": text[start : start + MAX_CHARS],
                    }
                )
    return out


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


class DocIndex:
    def __init__(self, client=None):
        self.client, self.docs, self.vectors = client, chunks(), None
        self.version = hashlib.sha256(repr(self.docs).encode()).hexdigest()[:16]

    async def _embed(self, texts: list[str]) -> np.ndarray:
        out = []
        for i in range(0, len(texts), 16):
            res = await self.client.embeddings.create(model=EMBED_MODEL, input=texts[i : i + 16])
            out += [d.embedding for d in res.data]
        v = np.array(out, dtype=np.float32)
        norms = np.linalg.norm(v, axis=1, keepdims=True)
        if not np.isfinite(v).all() or (norms == 0).any():
            raise ValueError("Invalid document embeddings")
        return v / norms

    async def search(self, query: str, k: int = 3) -> list[dict]:
        if self.client is not None:
            try:
                if self.vectors is None:
                    self.vectors = await asyncio.wait_for(
                        self._embed([d["text"] for d in self.docs]), timeout=5
                    )
                scores = self.vectors @ (await asyncio.wait_for(self._embed([query]), timeout=3))[0]
                return [self.docs[i] for i in np.argsort(-scores)[:k] if scores[i] >= 0.25]
            except Exception:
                pass  # AI service unreachable: fall back to keywords
        q = _words(query)
        ranked = sorted(
            (d for d in self.docs if q & _words(d["text"])),
            key=lambda d: len(q & _words(d["text"])),
            reverse=True,
        )
        return ranked[:k]
