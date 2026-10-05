"""Emulab agent: the campus network built from real Linux networking (Mininet + Open vSwitch).

Every campus device is an Open vSwitch bridge, every campus link a Mininet TCLink (real delay
and bandwidth via tc), and every building / the internet gateway has a host attached. The
NetHeal engine (services/netsim/emu.py) drives it over HTTP:

  POST /reset            routes for every flow -> OpenFlow 1.3 rules (ovs-ofctl), faults cleared
  GET  /telemetry        real measurements: pings per flow, port counters + tc stats per link
  POST /route            reroute one flow (replaces its OpenFlow rules)
  POST /fault            link down / gray loss / congestion / flapping / overload / blackhole
  POST /clear_faults, POST /rollback_config

Traffic is real: one iperf3 UDP stream per flow at its demand. Bandwidths are scaled by SCALE
(1 simulated Mbps = 10 kbit/s) so the whole campus fits in a laptop; telemetry is scaled back.
"""

import re
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import networkx as nx
import yaml
from fastapi import FastAPI
from mininet.link import TCLink
from mininet.net import Mininet
from mininet.node import OVSSwitch
from pydantic import BaseModel

SCALE = 0.01
PINGS, PING_GAP_S, PING_WAIT_S = 10, 0.01, 0.3
FLAP_PERIOD_S = 2.0
spec = yaml.safe_load(Path("campus.yaml").read_text())
lock = threading.RLock()  # Mininet node shells are not thread-safe

net: Mininet | None = None
sw: dict[str, object] = {}  # campus node -> switch
host: dict[str, object] = {}  # campus node -> attached host (buildings, internet, admin)
links: dict[str, dict] = {}  # link id -> {a, b, intf_a, intf_b, bw, delay}
flows = {f["id"]: f for f in spec["flows"]}
routes: dict[str, list[str]] = {}
faults: dict[str, dict] = {}  # link/node/flow -> active fault
counters: dict[str, tuple] = {}  # interface -> (time, tx_bytes, tc_sent_pkts, tc_dropped)
stop_bg = threading.Event()


def sh(cmd: str) -> str:
    with lock:
        return net.switches[0].cmd(cmd)  # root namespace shell


# ---- topology ---------------------------------------------------------------


def build() -> None:
    global net
    net = Mininet(switch=OVSSwitch, link=TCLink, controller=None, autoStaticArp=True)
    for i, n in enumerate(spec["nodes"], start=1):
        sw[n["id"]] = net.addSwitch(f"s{i}", failMode="secure", protocols="OpenFlow13")
    endpoints = {f["src"] for f in spec["flows"]} | {f["dst"] for f in spec["flows"]}
    for i, n in enumerate(sorted(endpoints), start=1):
        host[n] = net.addHost(f"h{i}", ip=f"10.0.0.{i}/24")
        net.addLink(host[n], sw[n])
    for link in spec["links"]:
        bw = max(1.0, link["capacity_mbps"] * SCALE)
        delay = f"{link['base_latency_ms']}ms"
        lk = net.addLink(sw[link["a"]], sw[link["b"]], bw=bw, delay=delay)
        links[f"{link['a']}-{link['b']}"] = {
            "a": link["a"], "b": link["b"], "intf_a": lk.intf1, "intf_b": lk.intf2,
            "bw": bw, "delay": delay,
        }  # fmt: skip
    net.start()


def port(a: str, b: str) -> int:
    """OpenFlow port on switch `a` that leads to campus node `b` (or to a's own host)."""
    if a == b:
        intf = next(
            i
            for i in sw[a].intfList()
            if i.link and host[a] in (i.link.intf1.node, i.link.intf2.node)
        )
    else:
        lk = links.get(f"{a}-{b}") or links[f"{b}-{a}"]
        intf = lk["intf_a"] if lk["a"] == a else lk["intf_b"]
    return sw[a].ports[intf]


def ofctl(switch, args: str) -> None:
    with lock:
        switch.cmd(f"ovs-ofctl -O OpenFlow13 {args}")


def install_route(flow_id: str, path: list[str]) -> None:
    f = flows[flow_id]
    src, dst = host[f["src"]].IP(), host[f["dst"]].IP()
    for a, b in ((src, dst), (dst, src)):  # remove both directions first
        for s in sw.values():
            ofctl(s, f"del-flows {s.name} 'ip,nw_src={a},nw_dst={b}'")
    hops = [*path, path[-1]]  # last switch hands the packet to its host
    for here, nxt in zip(hops, hops[1:], strict=False):
        ofctl(
            sw[here],
            f"add-flow {sw[here].name} 'priority=100,ip,nw_src={src},nw_dst={dst},"
            f"actions=output:{port(here, nxt)}'",
        )
    back = [*path[::-1], path[0]]
    for here, nxt in zip(back, back[1:], strict=False):
        ofctl(
            sw[here],
            f"add-flow {sw[here].name} 'priority=100,ip,nw_src={dst},nw_dst={src},"
            f"actions=output:{port(here, nxt)}'",
        )
    routes[flow_id] = path


def start_traffic() -> None:
    """One iperf3 UDP stream per flow at its (scaled) demand."""
    for i, f in enumerate(flows.values()):
        p = 5201 + i
        with lock:
            host[f["dst"]].cmd(f"iperf3 -s -p {p} -D")
        time.sleep(0.2)
        rate = f"{f['demand_mbps'] * SCALE:.2f}M"
        with lock:
            host[f["src"]].cmd(
                f"iperf3 -c {host[f['dst']].IP()} -p {p} -u -b {rate} -t 0 -l 1200 "
                "> /dev/null 2>&1 &"
            )


# ---- faults -----------------------------------------------------------------


def shape(
    link_id: str, bw_factor: float = 1.0, loss: float = 0.0, extra_delay_ms: float = 0.0
) -> None:
    lk = links[link_id]
    delay = f"{float(lk['delay'][:-2]) + extra_delay_ms}ms"
    with lock:
        for intf in (lk["intf_a"], lk["intf_b"]):
            intf.config(bw=lk["bw"] * bw_factor, delay=delay, loss=loss)


def set_link(link_id: str, up: bool) -> None:
    lk = links[link_id]
    with lock:
        net.configLinkStatus(lk["intf_a"].node.name, lk["intf_b"].node.name, "up" if up else "down")


def apply(target: str, f: dict, severity: float) -> None:
    kind = f["type"]
    if kind == "gray_failure":
        shape(target, loss=round(20 * severity, 1))
    elif kind == "congestion":
        shape(target, bw_factor=max(0.05, 1 - 0.8 * severity))
    elif kind == "node_overload":  # modelled as extra processing delay on all of the device's ports
        for lid, lk in links.items():
            if target in (lk["a"], lk["b"]):
                shape(lid, extra_delay_ms=20 * severity, loss=round(3 * severity, 1))


def fault_loop() -> None:
    """Background: ramps gradual faults up and makes flapping links flap."""
    while not stop_bg.wait(0.5):
        now = time.time()
        for target, f in list(faults.items()):
            if f["type"] == "flapping":
                set_link(target, int((now - f["start"]) / FLAP_PERIOD_S) % 2 == 1)
            elif f["ramp_s"] and f["type"] in ("gray_failure", "congestion", "node_overload"):
                apply(target, f, f["severity"] * min(1.0, (now - f["start"]) / f["ramp_s"]))


def inject(kind: str, target: str, severity: float, ramp_s: float) -> None:
    faults[target] = {"type": kind, "severity": severity, "ramp_s": ramp_s, "start": time.time()}
    if kind in ("link_down", "flapping"):
        set_link(target, False)
    elif kind == "misconfig":
        f = flows[target]
        src, dst = host[f["src"]].IP(), host[f["dst"]].IP()
        rule = f"priority=200,ip,nw_src={src},nw_dst={dst},actions=drop"
        ofctl(sw[f["src"]], f"add-flow {sw[f['src']].name} '{rule}'")
    elif not ramp_s:
        apply(target, faults[target], severity)


def clear(target: str) -> None:
    f = faults.pop(target)
    if f["type"] in ("link_down", "flapping"):
        set_link(target, True)
    elif f["type"] == "misconfig":
        fl = flows[target]
        ofctl(sw[fl["src"]], f"del-flows {sw[fl['src']].name} 'ip,nw_src={host[fl['src']].IP()},"
                             f"nw_dst={host[fl['dst']].IP()}'")  # fmt: skip
        install_route(target, routes[target])  # put the normal rules back
    elif f["type"] == "node_overload":
        for lid, lk in links.items():
            if target in (lk["a"], lk["b"]):
                shape(lid)
    else:
        shape(target)


# ---- telemetry --------------------------------------------------------------


def tc_stats(intf: str) -> tuple[int, int, int]:
    """(sent packets, dropped, backlog bytes) summed over the interface's qdiscs."""
    out = sh(f"tc -s qdisc show dev {intf}")
    sent = sum(int(x) for x in re.findall(r"Sent \d+ bytes (\d+) pkt", out))
    dropped = sum(int(x) for x in re.findall(r"dropped (\d+)", out))
    backlog = sum(int(x) for x in re.findall(r"backlog (\d+)b", out))
    return sent, dropped, backlog


def tx_bytes(intf: str) -> int:
    return int(sh(f"cat /sys/class/net/{intf}/statistics/tx_bytes").strip() or 0)


def link_sample(link_id: str, lk: dict) -> dict:
    base = {"entity_type": "link", "entity_id": link_id, "cpu": None}
    up = "UP" in sh(f"ip link show {lk['intf_a'].name}") and link_id not in [
        t for t, f in faults.items() if f["type"] == "link_down"]  # fmt: skip
    if not up:
        return {
            **base,
            "latency_ms": None,
            "loss_pct": 100.0,
            "throughput_mbps": 0.0,
            "util": 0.0,
            "queue_len": 0.0,
        }
    now, rate, sent, dropped, backlog = time.time(), 0.0, 0, 0, 0
    for intf in (lk["intf_a"].name, lk["intf_b"].name):
        b = tx_bytes(intf)
        s, d, q = tc_stats(intf)
        t0, b0, s0, d0 = counters.get(intf, (now, b, s, d))
        counters[intf] = (now, b, s, d)
        dt = max(now - t0, 1e-3)
        rate = max(rate, (b - b0) * 8 / dt / 1e6)  # busier direction, Mbit/s (scaled)
        sent, dropped, backlog = sent + (s - s0), dropped + (d - d0), max(backlog, q)
    util = rate / lk["bw"]
    queue_ms = backlog * 8 / (lk["bw"] * 1e6) * 1000
    return {**base, "latency_ms": float(lk["delay"][:-2]) + queue_ms + _extra_delay(link_id),
            "loss_pct": 100 * dropped / max(sent + dropped, 1), "throughput_mbps": rate / SCALE,
            "util": util, "queue_len": backlog / 1500}  # fmt: skip


def _extra_delay(link_id: str) -> float:
    lk = links[link_id]
    return sum(20 * f["severity"] for t, f in faults.items()
               if f["type"] == "node_overload" and t in (lk["a"], lk["b"]))  # fmt: skip


def node_samples(link_rows: dict) -> list[dict]:
    """Switch CPU can't be measured in emulation: modelled from traffic + injected overload."""
    out = []
    for n in sw:
        attached = [lid for lid in links if n in (links[lid]["a"], links[lid]["b"])]
        traffic = sum(link_rows[lid]["throughput_mbps"] for lid in attached)
        capacity = sum(links[lid]["bw"] / SCALE for lid in attached) / 2
        f = faults.get(n)
        extra = 0.9 * f["severity"] if f and f["type"] == "node_overload" else 0.0
        cpu = min(0.99, 0.15 + 0.3 * min(1.0, traffic / capacity) + extra)
        out.append({
            "entity_type": "node", "entity_id": n, "cpu": cpu, "latency_ms": None,
            "loss_pct": 0.0, "throughput_mbps": traffic, "util": None, "queue_len": None,
        })  # fmt: skip
    return out


def flow_samples() -> list[dict]:
    with lock:
        args = ["ping", "-c", str(PINGS), "-i", str(PING_GAP_S), "-W", str(PING_WAIT_S), "-q"]
        procs = {
            fid: host[f["src"]].popen([*args, host[f["dst"]].IP()]) for fid, f in flows.items()
        }
    out = []
    for fid, p in procs.items():
        text = p.communicate()[0].decode() if p.stdout else ""
        loss = float(m.group(1)) if (m := re.search(r"([\d.]+)% packet loss", text)) else 100.0
        rtt = float(m.group(1)) if (m := re.search(r"= [\d.]+/([\d.]+)/", text)) else None
        out.append({
            "entity_type": "flow", "entity_id": fid,
            "latency_ms": None if rtt is None else rtt / 2,  # one-way, like the simulator
            "loss_pct": loss, "throughput_mbps": flows[fid]["demand_mbps"] * (1 - loss / 100),
            "util": None, "cpu": None, "queue_len": None,
        })  # fmt: skip
    return out


# ---- API --------------------------------------------------------------------

ready = False


@asynccontextmanager
async def lifespan(_: FastAPI):
    global ready
    build()
    g = nx.Graph([(lk["a"], lk["b"]) for lk in links.values()])
    for fid, f in flows.items():  # until the engine sends its own routes
        install_route(fid, nx.shortest_path(g, f["src"], f["dst"]))
    start_traffic()
    threading.Thread(target=fault_loop, daemon=True).start()
    ready = True
    yield
    stop_bg.set()
    net.stop()


app = FastAPI(title="NetHeal Emulab", lifespan=lifespan)


class Reset(BaseModel):
    routes: dict[str, list[str]]


class Route(BaseModel):
    flow: str
    path: list[str]


class Fault(BaseModel):
    type: str
    target: str
    severity: float = 1.0
    ramp_s: float = 0.0


class Target(BaseModel):
    flow: str


@app.get("/health")
def health() -> dict:
    return {"ready": ready, "switches": len(sw), "hosts": len(host), "links": len(links)}


@app.post("/reset")
def reset(req: Reset) -> dict:
    for target in list(faults):
        clear(target)
    for fid, path in req.routes.items():
        install_route(fid, path)
    return {"ok": True}


@app.post("/route")
def route(req: Route) -> dict:
    install_route(req.flow, req.path)
    return {"ok": True}


@app.post("/fault")
def fault(req: Fault) -> dict:
    inject(req.type, req.target, req.severity, req.ramp_s)
    return {"ok": True}


@app.post("/clear_faults")
def clear_faults() -> dict:
    for target in list(faults):
        clear(target)
    return {"ok": True}


@app.post("/rollback_config")
def rollback_config(req: Target) -> dict:
    if faults.get(req.flow, {}).get("type") == "misconfig":
        clear(req.flow)
    return {"ok": True}


@app.get("/telemetry")
def telemetry() -> list[dict]:
    link_rows = {lid: link_sample(lid, lk) for lid, lk in links.items()}
    return [*link_rows.values(), *node_samples(link_rows), *flow_samples()]
