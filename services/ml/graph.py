"""Entity graph for the root-cause GNN, built the same way for training and live inference.

Vertices: every device (node), every link and every traffic flow.
Edges:    link <-> its two devices, flow <-> every link and device on its current route.
So a message-passing GNN can learn both the physical topology and 007-style "which
element do the suffering flows share" reasoning.
"""

import numpy as np
import torch

from services.detector.detector import METRICS
from services.netsim.engine import Network

CAUSES = [
    "none", "link_failure", "gray_failure", "congestion", "flapping", "node_overload", "misconfig",
]  # fmt: skip
# Which causes each kind of vertex can have (used to mask predictions).
VALID = {
    "link": {"link_failure", "gray_failure", "congestion", "flapping"},
    "node": {"node_overload"},
    "flow": {"misconfig"},
}
KINDS = ["node", "link", "flow"]
NUM_FEATURES = 13


class EntityGraph:
    """Static structure (vertex order + edges) for one topology and routing."""

    def __init__(self, net: Network):
        self.ids = [*net.graph.nodes, *net.links, *net.flows]
        self.kinds = (
            ["node"] * len(net.graph.nodes) + ["link"] * len(net.links) + ["flow"] * len(net.flows)
        )
        index = {v: i for i, v in enumerate(self.ids)}
        pairs = []
        for lid, (a, b) in net.links.items():
            pairs += [(index[lid], index[a]), (index[lid], index[b])]
        for fid, route in net.routes.items():
            on_route = [*route, *net.path_links(route)]
            pairs += [(index[fid], index[x]) for x in on_route]
        src, dst = zip(*pairs, strict=True)
        self.edge_index = torch.tensor([src + dst, dst + src], dtype=torch.long)  # undirected
        self.index = index


def features(graph: EntityGraph, latest, detector, link_flips: dict[str, int]) -> torch.Tensor:
    """NUM_FEATURES per vertex from current telemetry, the detector's baseline and alerts."""
    x = np.zeros((len(graph.ids), NUM_FEATURES), dtype=np.float32)
    for i, (entity, kind) in enumerate(zip(graph.ids, graph.kinds, strict=True)):
        s = latest[entity]
        x[i, KINDS.index(kind)] = 1.0
        down = kind != "node" and s.latency_ms is None
        if entity in detector.median and not down:
            values = np.array([getattr(s, m) for m in METRICS[kind]], dtype=float)
            z = (values - detector.median[entity]) / detector.scale[entity]
            x[i, 3 : 3 + len(z)] = np.clip(z, -10, 50) / 10
        x[i, 6] = float(down)
        anomaly = detector.active.get(entity)
        x[i, 7] = float(anomaly is not None)
        x[i, 8] = float(anomaly is not None and anomaly.severity == "critical")
        x[i, 9] = min(link_flips.get(entity, 0), 5) / 5
        x[i, 10] = min(s.util if s.util is not None else (s.cpu or 0.0), 2.0)
        x[i, 11] = (s.loss_pct or 0.0) / 100
        x[i, 12] = float((s.throughput_mbps or 0.0) > 1)
    return torch.from_numpy(x)


def link_flips(rca) -> dict[str, int]:
    """Up/down transitions per link in the RCA engine's recent history."""
    return {
        lid: sum(a != b for a, b in zip(h, list(h)[1:], strict=False))
        for lid, h in rca.link_down.items()
    }
