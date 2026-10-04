"""Discrete-time campus network simulator (the digital twin).

Every tick (TICK_S seconds of simulated time) it routes the traffic demands,
computes link utilisation, and derives latency, loss, throughput and CPU from a
simple queueing model. Faults change link/node state; routes only change when
someone calls set_route() (the SDN controller role), so a fault stays broken
until it is healed.
"""

import copy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import networkx as nx
import numpy as np

from contracts.models import TelemetrySample, new_id
from services.netsim.topology import DEFAULT_TOPOLOGY, load_topology

TICK_S = 0.5
QUEUE_MS = 2.0  # queueing delay scale: QUEUE_MS * util / (1 - util)
NODE_PROC_MS = 1.0  # processing delay scale for a busy node
MAX_UTIL = 0.99
FLAP_PERIOD_TICKS = 4

FAULT_TYPES = {"link_down", "gray_failure", "congestion", "flapping", "node_overload", "misconfig"}
LINK_FAULTS = {"link_down", "gray_failure", "congestion", "flapping"}


@dataclass
class Fault:
    id: str
    type: str
    target: str
    severity: float
    ramp_ticks: int
    start_tick: int


class Network:
    def __init__(self, seed: int = 42, t0: datetime | None = None, path: Path = DEFAULT_TOPOLOGY):
        self.graph = load_topology(path)
        self.links = {d["id"]: (a, b) for a, b, d in self.graph.edges(data=True)}
        self.flows = {f["id"]: f for f in self.graph.graph["flows"]}
        self.routes = {
            fid: nx.shortest_path(self.graph, f["src"], f["dst"], weight="base_latency_ms")
            for fid, f in self.flows.items()
        }
        self.faults: dict[str, Fault] = {}
        self.rng = np.random.default_rng(seed)
        self.t0 = t0 or datetime(2026, 1, 1, tzinfo=UTC)
        self.tick = 0

    # ---- control -------------------------------------------------------

    def inject_fault(
        self, type: str, target: str, severity: float = 1.0, ramp_s: float = 0.0
    ) -> Fault:
        if type not in FAULT_TYPES:
            raise ValueError(f"unknown fault type {type!r}")
        valid = (
            self.links
            if type in LINK_FAULTS
            else self.flows
            if type == "misconfig"
            else self.graph.nodes
        )
        if target not in valid:
            raise ValueError(f"unknown target {target!r} for {type}")
        fault = Fault(new_id(), type, target, severity, round(ramp_s / TICK_S), self.tick)
        self.faults[fault.id] = fault
        return fault

    def clear_faults(self) -> None:
        self.faults.clear()

    def rollback_config(self, flow_id: str) -> None:
        """Restore a flow's last known-good forwarding rules (undoes a misconfig)."""
        self.faults = {
            k: f for k, f in self.faults.items() if (f.type, f.target) != ("misconfig", flow_id)
        }

    @property
    def now(self) -> datetime:
        return self.t0 + timedelta(seconds=self.tick * TICK_S)

    def set_route(self, flow_id: str, path: list[str]) -> None:
        f = self.flows[flow_id]
        if path[0] != f["src"] or path[-1] != f["dst"] or not nx.is_path(self.graph, path):
            raise ValueError(f"invalid path for {flow_id}: {path}")
        self.routes[flow_id] = path

    def snapshot(self) -> "Network":
        """Independent copy for what-if dry runs."""
        return copy.deepcopy(self)

    # ---- simulation ----------------------------------------------------

    def _severity(self, f: Fault) -> float:
        if f.ramp_ticks == 0:
            return f.severity
        return f.severity * min(1.0, (self.tick - f.start_tick) / f.ramp_ticks)

    def _fault_state(self):
        down, extra_loss, extra_load, extra_cpu, blackholed = set(), {}, {}, {}, set()
        for f in self.faults.values():
            sev = self._severity(f)
            if f.type == "link_down":
                down.add(f.target)
            elif f.type == "flapping":
                if ((self.tick - f.start_tick) // FLAP_PERIOD_TICKS) % 2 == 0:
                    down.add(f.target)
            elif f.type == "gray_failure":
                extra_loss[f.target] = extra_loss.get(f.target, 0) + 20.0 * sev
            elif f.type == "congestion":
                a, b = self.links[f.target]
                cap = self.graph.edges[a, b]["capacity_mbps"]
                extra_load[f.target] = extra_load.get(f.target, 0) + sev * cap
            elif f.type == "node_overload":
                extra_cpu[f.target] = extra_cpu.get(f.target, 0) + 0.9 * sev
            elif f.type == "misconfig":
                blackholed.add(f.target)
        return down, extra_loss, extra_load, extra_cpu, blackholed

    def path_links(self, path: list[str]) -> list[str]:
        return [self.graph.edges[a, b]["id"] for a, b in zip(path, path[1:], strict=False)]

    def step(self) -> list[TelemetrySample]:
        self.tick += 1
        ts = self.now
        down, extra_loss, extra_load, extra_cpu, blackholed = self._fault_state()

        # Traffic that reaches its destination loads every link on its path.
        reachable = {
            fid: not (fid in blackholed or down.intersection(self.path_links(path)))
            for fid, path in self.routes.items()
        }
        load = dict.fromkeys(self.links, 0.0)
        for lid, extra in extra_load.items():
            load[lid] += extra
        for fid, path in self.routes.items():
            if reachable[fid]:
                for lid in self.path_links(path):
                    load[lid] += self.flows[fid]["demand_mbps"]

        samples: list[TelemetrySample] = []
        link_lat, link_loss = {}, {}
        for lid, (a, b) in self.links.items():
            e = self.graph.edges[a, b]
            if lid in down:
                link_loss[lid] = 100.0
                samples.append(
                    TelemetrySample(
                        ts=ts,
                        entity_type="link",
                        entity_id=lid,
                        latency_ms=None,
                        loss_pct=100.0,
                        throughput_mbps=0.0,
                        util=0.0,
                        queue_len=0.0,
                    )
                )
                continue
            util = load[lid] / e["capacity_mbps"]
            u = min(util, MAX_UTIL)
            latency = (e["base_latency_ms"] + QUEUE_MS * u / (1 - u)) * self._noise(0.03)
            loss = 100 * max(0.0, 1 - 1 / util) if util > 1 else 0.0
            loss += 3.0 * max(0.0, (u - 0.85) / 0.15) ** 2
            loss = min(100.0, loss + extra_loss.get(lid, 0.0) + abs(self.rng.normal(0, 0.02)))
            link_lat[lid], link_loss[lid] = latency, loss
            samples.append(
                TelemetrySample(
                    ts=ts,
                    entity_type="link",
                    entity_id=lid,
                    latency_ms=latency,
                    loss_pct=loss,
                    throughput_mbps=min(load[lid], e["capacity_mbps"])
                    * (1 - loss / 100)
                    * self._noise(0.01),
                    util=util,
                    queue_len=u / (1 - u),
                )
            )

        node_delay, node_loss = {}, {}
        for n in self.graph.nodes:
            edges = self.graph.edges(n, data=True)
            traffic = sum(load[d["id"]] for _, _, d in edges if d["id"] not in down)
            capacity = sum(d["capacity_mbps"] for _, _, d in edges) / 2
            cpu = min(MAX_UTIL, 0.15 + 0.3 * min(1.0, traffic / capacity) + extra_cpu.get(n, 0))
            node_delay[n] = NODE_PROC_MS * cpu / (1 - cpu)
            node_loss[n] = 10.0 * max(0.0, (cpu - 0.95) / 0.05)
            samples.append(
                TelemetrySample(
                    ts=ts,
                    entity_type="node",
                    entity_id=n,
                    cpu=cpu * self._noise(0.02),
                    latency_ms=node_delay[n],
                    loss_pct=node_loss[n],
                    throughput_mbps=traffic,
                )
            )

        for fid, path in self.routes.items():
            demand = self.flows[fid]["demand_mbps"]
            if not reachable[fid]:
                samples.append(
                    TelemetrySample(
                        ts=ts,
                        entity_type="flow",
                        entity_id=fid,
                        latency_ms=None,
                        loss_pct=100.0,
                        throughput_mbps=0.0,
                    )
                )
                continue
            links = self.path_links(path)
            latency = sum(link_lat[lid] for lid in links) + sum(node_delay[n] for n in path)
            delivered = np.prod([1 - link_loss[lid] / 100 for lid in links])
            delivered *= np.prod([1 - node_loss[n] / 100 for n in path])
            samples.append(
                TelemetrySample(
                    ts=ts,
                    entity_type="flow",
                    entity_id=fid,
                    latency_ms=latency,
                    loss_pct=100 * (1 - delivered),
                    throughput_mbps=demand * delivered,
                )
            )
        return samples

    def _noise(self, sigma: float) -> float:
        return float(1 + self.rng.normal(0, sigma))
