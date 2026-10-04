from pathlib import Path

import networkx as nx
import yaml

DEFAULT_TOPOLOGY = Path(__file__).resolve().parents[2] / "topology" / "campus.yaml"


def link_id(a: str, b: str) -> str:
    return f"{a}-{b}"


def load_topology(path: Path = DEFAULT_TOPOLOGY) -> nx.Graph:
    spec = yaml.safe_load(path.read_text())
    g = nx.Graph()
    for node in spec["nodes"]:
        g.add_node(node["id"], layer=node["layer"], name=node["name"])
    for link in spec["links"]:
        g.add_edge(
            link["a"],
            link["b"],
            id=link_id(link["a"], link["b"]),
            capacity_mbps=link["capacity_mbps"],
            base_latency_ms=link["base_latency_ms"],
        )
    return g
