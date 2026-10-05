"""Synthetic labelled data from the simulator (our digital twin is our data source).

Each scenario: copy a warmed-up network + detector + RCA, inject one random fault
(type, target, severity, sudden or gradual), run it, and record
  - rca:    entity-graph snapshots at the first diagnosis and +2 / +6 ticks, with the
            true root cause, plus what the rules and voting-only would have answered
  - series: per-flow latency/loss over time (+ healthy baseline) for the forecaster
Healthy scenarios (no fault) are mixed in for negatives.
"""

import copy
from multiprocessing import Pool

import numpy as np

from services.detector.detector import WARMUP_TICKS, Detector
from services.ml.graph import CAUSES, EntityGraph, features, link_flips
from services.netsim.engine import Network
from services.rca.engine import RCAEngine

FAULT_TO_CAUSE = {
    "link_down": "link_failure", "gray_failure": "gray_failure", "congestion": "congestion",
    "flapping": "flapping", "node_overload": "node_overload", "misconfig": "misconfig",
}  # fmt: skip
PRE_TICKS, POST_TICKS = 12, 40
SNAPSHOT_OFFSETS = (0, 2, 6)  # ticks after the first diagnosis
BASE_SEEDS = (101, 202, 303, 404)

_bases: dict[int, tuple] = {}


def base(seed: int):
    """A network + detector + RCA warmed up on healthy traffic (cached per process)."""
    if seed not in _bases:
        net, det, rca = Network(seed=seed), Detector(), RCAEngine()
        for _ in range(WARMUP_TICKS):
            samples = net.step()
            det.update(samples)
            rca.update(samples, det.active, net)
        _bases[seed] = (net, det, rca)
    return _bases[seed]


def random_fault(rng: np.random.Generator, net: Network):
    kind = rng.choice([*FAULT_TO_CAUSE, "none"], p=[0.15] * 6 + [0.1])
    if kind == "none":
        return None
    if kind == "misconfig":
        target = rng.choice(list(net.flows))
    elif kind == "node_overload":
        target = rng.choice([n for n in net.graph.nodes if n != "internet"])
    else:
        target = rng.choice(list(net.links))
    severity = 1.0 if kind in ("link_down", "flapping", "misconfig") else rng.uniform(0.3, 1.0)
    return str(kind), str(target), float(severity), float(rng.choice([0, 0, 5, 10, 20, 30]))


def voting_only(net: Network, active) -> str | None:
    """007 alone (Arzani et al., NSDI'18): each suffering flow gives 1/len(path) votes to every
    link on its path; the most-voted link is blamed. No fault signatures, links only."""
    bad = [f for f in net.flows if f in active]
    if not bad:
        return None
    votes = dict.fromkeys(net.links, 0.0)
    for f in bad:
        path = net.path_links(net.routes[f])
        for lid in path:
            votes[lid] += 1 / len(path)
    return max(votes, key=votes.get)


def scenario(seed: int) -> dict:
    rng = np.random.default_rng(seed)
    net, det, rca = (copy.deepcopy(x) for x in base(BASE_SEEDS[seed % len(BASE_SEEDS)]))
    net.rng = np.random.default_rng(seed)
    fault = random_fault(rng, net)
    baseline = {f: float(det.median[f][0]) for f in net.flows}
    series = {f: [] for f in net.flows}
    rca_snaps, first_diag = [], None

    for t in range(PRE_TICKS + POST_TICKS):
        if t == PRE_TICKS and fault:
            net.inject_fault(*fault)
        samples = net.step()
        det.update(samples)
        rca.update(samples, det.active, net)
        latest = {s.entity_id: s for s in samples}
        for f in net.flows:
            series[f].append((latest[f].latency_ms, latest[f].loss_pct))

        if fault and rca.hypotheses and first_diag is None:
            first_diag = t
        if first_diag is not None and t - first_diag in SNAPSHOT_OFFSETS:
            graph = EntityGraph(net)
            y = np.zeros(len(graph.ids), dtype=np.int64)
            y[graph.index[fault[1]]] = CAUSES.index(FAULT_TO_CAUSE[fault[0]])
            rca_snaps.append({
                "offset": t - first_diag,
                "x": features(graph, latest, det, link_flips(rca)),
                "edge_index": graph.edge_index,
                "y": y,
                "ids": graph.ids,
                "kinds": graph.kinds,
                "rules": [
                    (h.cause, h.target, h.method_scores["signature"], h.method_scores["voting"])
                    for h in rca.hypotheses
                ],
                "voting_target": voting_only(net, det.active),
            })  # fmt: skip
    return {
        "seed": seed,
        "fault": fault,
        "onset": PRE_TICKS,
        "detected": first_diag is not None,
        "baseline": baseline,
        "series": series,
        "rca": rca_snaps,
    }


def generate(seeds: list[int], processes: int = 8) -> list[dict]:
    with Pool(processes) as pool:
        return pool.map(scenario, seeds, chunksize=16)
