"""Unit tests for provenance independence analysis."""
import pytest
from app.core.provenance import ProvenanceGraph, ProvenanceNode


def make_graph(*nodes):
    g = ProvenanceGraph()
    for n in nodes:
        g.add_node(n)
    return g


class TestProvenanceGraph:
    def test_single_origin_collapse(self):
        """3 records from same origin = 1 independent lineage."""
        g = make_graph(
            ProvenanceNode("ORIG", "origin"),
            ProvenanceNode("DS1", "dataset", ["ORIG"]),
            ProvenanceNode("DS2", "dataset", ["ORIG"]),
            ProvenanceNode("REC-A", "record", ["DS1"]),
            ProvenanceNode("REC-B", "record", ["DS2"]),
            ProvenanceNode("REC-C", "record", ["DS1"]),
        )
        r = g.analyze_independence(["REC-A", "REC-B", "REC-C"])
        assert r.independent_lineages == 1
        assert not r.is_independent
        assert not r.unknown

    def test_two_independent_origins(self):
        g = make_graph(
            ProvenanceNode("O1", "origin"),
            ProvenanceNode("O2", "origin"),
            ProvenanceNode("D1", "dataset", ["O1"]),
            ProvenanceNode("D2", "dataset", ["O2"]),
            ProvenanceNode("R1", "record", ["D1"]),
            ProvenanceNode("R2", "record", ["D2"]),
        )
        r = g.analyze_independence(["R1", "R2"])
        assert r.independent_lineages == 2
        assert r.is_independent

    def test_three_origins(self):
        g = make_graph(
            ProvenanceNode("O1", "origin"),
            ProvenanceNode("O2", "origin"),
            ProvenanceNode("O3", "origin"),
            ProvenanceNode("R1", "record", ["O1"]),
            ProvenanceNode("R2", "record", ["O2"]),
            ProvenanceNode("R3", "record", ["O3"]),
        )
        r = g.analyze_independence(["R1", "R2", "R3"])
        assert r.independent_lineages == 3

    def test_missing_node_returns_unknown(self):
        g = make_graph(ProvenanceNode("ORIG", "origin"))
        r = g.analyze_independence(["NONEXISTENT"])
        assert r.unknown

    def test_cycle_detected(self):
        g = make_graph(
            ProvenanceNode("A", "dataset", ["B"]),
            ProvenanceNode("B", "dataset", ["A"]),
            ProvenanceNode("R", "record", ["A"]),
        )
        r = g.analyze_independence(["R"])
        assert r.unknown
        assert "cycle" in r.reason.lower()

    def test_metadata_independence_ignored(self):
        """Metadata claims of 'independent source' should NOT override graph."""
        g = make_graph(
            ProvenanceNode("ORIG", "origin"),
            ProvenanceNode("DS1", "dataset", ["ORIG"], metadata={"independent": True}),
            ProvenanceNode("DS2", "dataset", ["ORIG"], metadata={"independent": True}),
            ProvenanceNode("R1", "record", ["DS1"]),
            ProvenanceNode("R2", "record", ["DS2"]),
        )
        r = g.analyze_independence(["R1", "R2"])
        # Despite metadata claim, both descend from same origin
        assert r.independent_lineages == 1

    def test_empty_records(self):
        g = make_graph(ProvenanceNode("ORIG", "origin"))
        r = g.analyze_independence([])
        assert r.unknown

    def test_to_dict(self):
        g = make_graph(
            ProvenanceNode("O", "origin"),
            ProvenanceNode("R", "record", ["O"]),
        )
        d = g.to_dict()
        assert "nodes" in d
        assert "edges" in d
        assert len(d["nodes"]) == 2
        assert len(d["edges"]) == 1
