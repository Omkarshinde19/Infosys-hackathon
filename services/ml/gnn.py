"""Root-cause GNN (GraphSAGE over the entity graph) and its ensemble with the rules.

The model classifies every vertex as "none" or one of the six causes valid for its kind.
The root cause is the vertex/cause pair with the highest probability.
"""

from pathlib import Path

import torch
from torch import nn
from torch_geometric.nn import SAGEConv

from services.ml.graph import CAUSES, NUM_FEATURES, VALID

MODEL_PATH = Path(__file__).parent / "models" / "rca_gnn.pt"
HIDDEN = 64
# Ensemble weights: fault signature (rules), 007 vote share, GNN probability.
W_SIGNATURE, W_VOTE, W_GNN = 0.45, 0.25, 0.30


class RootCauseGNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.convs = nn.ModuleList(
            [SAGEConv(NUM_FEATURES, HIDDEN), SAGEConv(HIDDEN, HIDDEN), SAGEConv(HIDDEN, HIDDEN)]
        )
        self.head = nn.Linear(HIDDEN, len(CAUSES))

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        for conv in self.convs:
            x = torch.relu(conv(x, edge_index))
        return self.head(x)  # logits per vertex


def valid_mask(kinds: list[str]) -> torch.Tensor:
    """True where a (vertex, cause) pair is possible; 'none' is excluded."""
    return torch.tensor([[c in VALID[k] for c in CAUSES] for k in kinds])


@torch.no_grad()
def probabilities(model: RootCauseGNN, x, edge_index, kinds) -> torch.Tensor:
    probs = torch.softmax(model(x, edge_index), dim=1)
    return probs * valid_mask(kinds)


def top(probs: torch.Tensor, ids: list[str]) -> tuple[str, str, float]:
    """(cause, target, probability) of the most likely root cause."""
    flat = int(probs.argmax())
    vertex, cause = divmod(flat, len(CAUSES))
    return CAUSES[cause], ids[vertex], float(probs.flatten()[flat])


def ensemble(rules: list[tuple], probs: torch.Tensor, ids: list[str]) -> list[tuple]:
    """Combine rule hypotheses (cause, target, signature, vote) with the GNN.

    Returns (cause, target, confidence, gnn_probability) best first. If the GNN's own top
    pick isn't among the rule hypotheses it is added with signature 0 and vote 0.5.
    """
    index = {v: i for i, v in enumerate(ids)}

    def p(cause: str, target: str) -> float:
        return float(probs[index[target], CAUSES.index(cause)])

    candidates = [(c, t, s, v) for c, t, s, v in rules]
    g_cause, g_target, _ = top(probs, ids)
    if all((c, t) != (g_cause, g_target) for c, t, *_ in candidates):
        candidates.append((g_cause, g_target, 0.0, 0.5))
    ranked = [
        (c, t, W_SIGNATURE * s + W_VOTE * v + W_GNN * p(c, t), p(c, t)) for c, t, s, v in candidates
    ]
    return sorted(ranked, key=lambda r: r[2], reverse=True)


def load(path: Path = MODEL_PATH) -> RootCauseGNN | None:
    if not path.exists():
        return None
    model = RootCauseGNN()
    model.load_state_dict(torch.load(path, weights_only=True))
    return model.eval()
