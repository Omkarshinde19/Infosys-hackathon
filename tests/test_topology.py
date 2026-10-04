import networkx as nx

from services.netsim.topology import load_topology


def test_campus_layers():
    g = load_topology()
    layers = nx.get_node_attributes(g, "layer")
    assert list(layers.values()).count("core") == 2
    assert list(layers.values()).count("distribution") == 4
    assert list(layers.values()).count("access") == 8


def test_every_building_has_two_independent_paths_to_internet():
    g = load_topology()
    for node, layer in g.nodes(data="layer"):
        if layer == "access":
            assert nx.edge_connectivity(g, node, "internet") >= 2, node
