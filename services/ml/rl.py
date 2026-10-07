"""RL routing agent: proposes which flows to move, and where, as one more candidate fix.

A PPO policy (Stable-Baselines3) looks at the network's telemetry and the diagnosed fault and
picks one of K candidate paths for every flow. Its proposal is never applied directly: it
joins the rule-based candidates, is dry-run on the digital twin and must pass the OPA
guardrails like any other fix. Twin + policy act as a safety shield, and the agent was
trained in the twin against exactly that judgement (ml/train_rl.py).
"""

from itertools import islice
from pathlib import Path

import networkx as nx
import numpy as np

from services.netsim.engine import Network

MODEL_PATH = Path(__file__).parent / "models" / "rl_router.zip"
K = 8  # candidate paths per flow: every distribution x core combination on the campus
LATENCY_SCALE_MS = 100.0


class RoutingSpace:
    """Fixed-size view of a topology: entity order for observations, K paths per flow."""

    def __init__(self, net: Network):
        self.flows = list(net.flows)
        self.links = list(net.links)
        self.nodes = list(net.graph.nodes)
        self.targets = self.links + self.nodes
        self.paths = {}
        for fid, f in net.flows.items():
            paths = nx.shortest_simple_paths(net.graph, f["src"], f["dst"], "base_latency_ms")
            options = list(islice(paths, K))
            self.paths[fid] = options + [options[-1]] * (K - len(options))
        self.size = 3 * len(self.links) + len(self.nodes) + len(self.flows) * (2 + K + 1)
        self.size += len(self.targets)

    def observe(self, net: Network, latest: dict, target: str) -> np.ndarray:
        """Telemetry + current routes + the diagnosed fault location, as one vector."""
        x = []
        for lid in self.links:
            s = latest[lid]
            x += [s.util or 0.0, (s.loss_pct or 0.0) / 100, _latency(s.latency_ms)]
        x += [latest[n].cpu or 0.0 for n in self.nodes]
        for fid in self.flows:
            s = latest[fid]
            current = np.zeros(K + 1)  # one-hot of the current path; last slot = none of K
            current[self._index(fid, net.routes[fid])] = 1
            x += [(s.loss_pct or 0.0) / 100, _latency(s.latency_ms), *current]
        x += [float(t == target) for t in self.targets]
        return np.asarray(x, dtype=np.float32)

    def routes(self, action, net: Network) -> dict[str, list[str]]:
        """The flows whose path the action changes, and their new paths."""
        chosen = {f: self.paths[f][int(a)] for f, a in zip(self.flows, action, strict=True)}
        return {f: p for f, p in chosen.items() if p != net.routes[f]}

    def _index(self, fid: str, path: list[str]) -> int:
        return self.paths[fid].index(path) if path in self.paths[fid] else K


def _latency(ms: float | None) -> float:
    return 1.0 if ms is None else min(ms / LATENCY_SCALE_MS, 1.0)


class RLPlanner:
    def __init__(self, model):
        self.model = model
        self.space: RoutingSpace | None = None
        self.last_error: str | None = None
        self.schema = None

    def propose(self, net: Network, latest: dict, target: str) -> dict[str, list[str]]:
        """New routes for the flows the agent wants to move (empty: it would move nothing)."""
        self.last_error = None
        try:
            schema = (
                tuple(net.links),
                tuple(net.graph.nodes),
                tuple((fid, f["src"], f["dst"]) for fid, f in net.flows.items()),
                tuple(sorted(tuple(sorted(edge)) for edge in net.graph.edges)),
            )
            if self.space is None:
                self.space, self.schema = RoutingSpace(net), schema
            if schema != self.schema:
                raise ValueError("Topology/entity ordering differs from the routing vocabulary")
            if target not in self.space.targets:
                raise ValueError("Routing target is outside the policy observation schema")
            observation = self.space.observe(net, latest, target)
            expected = getattr(getattr(self.model, "observation_space", None), "shape", None)
            if not np.isfinite(observation).all() or (expected and observation.shape != expected):
                raise ValueError("Non-finite or incompatible routing observation")
            action, _ = self.model.predict(observation, deterministic=True)
            action = np.asarray(action)
            if (
                action.shape != (len(self.space.flows),)
                or not np.isfinite(action).all()
                or np.any(action != np.floor(action))
                or np.any((action < 0) | (action >= K))
            ):
                raise ValueError("Routing model returned an invalid candidate-path action")
            return self.space.routes(action, net)
        except Exception as error:
            # Optional model failures must leave deterministic guarded planning available.
            self.last_error = f"{type(error).__name__}: {error}"
            return {}


def load(path: Path = MODEL_PATH) -> RLPlanner | None:
    if not path.exists():
        return None
    from stable_baselines3 import PPO

    return RLPlanner(PPO.load(path, device="cpu"))
