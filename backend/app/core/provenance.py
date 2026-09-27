"""Provenance DAG and source independence analysis.

Core insight: 4 datasets sharing one origin = 1 independent observation.
The system traces the lineage graph to find distinct root origins — not
metadata claims, not source names.

W3C PROV-inspired model:
  - Entity: dataset, feature, survey observation, imagery
  - Activity: import, transform, reproject, extract, harmonize
  - Agent: survey agency, department, software
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProvenanceNode:
    node_id: str
    node_type: str      # "origin" | "dataset" | "transformation" | "record" | "agent" | "activity"
    parent_ids: list[str] = field(default_factory=list)
    content_hash: Optional[str] = None
    label: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class IndependenceResult:
    independent_lineages: int       # number of distinct origin nodes
    origins: list[str]              # origin node_ids
    is_independent: bool            # True if > 1 distinct origins
    unknown: bool                   # True if provenance incomplete
    reason: str
    lineage_map: dict[str, str] = field(default_factory=dict)  # record_id → origin_id


class ProvenanceGraph:
    """DAG of provenance nodes. Supports independence analysis."""

    def __init__(self):
        self._nodes: dict[str, ProvenanceNode] = {}

    def add_node(self, node: ProvenanceNode) -> None:
        self._nodes[node.node_id] = node

    def get(self, node_id: str) -> Optional[ProvenanceNode]:
        return self._nodes.get(node_id)

    def all_nodes(self) -> list[ProvenanceNode]:
        return list(self._nodes.values())

    def to_dict(self) -> dict:
        """Serialize graph for API export."""
        nodes = [
            {
                "node_id": n.node_id,
                "node_type": n.node_type,
                "parent_ids": n.parent_ids,
                "label": n.label,
                "content_hash": n.content_hash,
                "metadata": n.metadata,
            }
            for n in self._nodes.values()
        ]
        edges = [
            {"from": n.node_id, "to": parent}
            for n in self._nodes.values()
            for parent in n.parent_ids
        ]
        return {"nodes": nodes, "edges": edges}

    def _find_origins(self, node_id: str, visited: frozenset) -> set[str]:
        """DFS to all reachable origin nodes. Detects cycles."""
        if node_id in visited:
            raise RecursionError(f"cycle detected at {node_id!r}")
        visited = visited | {node_id}
        node = self._nodes.get(node_id)
        if node is None:
            raise KeyError(f"node {node_id!r} not in provenance graph")
        if node.node_type == "origin":
            return {node_id}
        if not node.parent_ids:
            raise ValueError(f"non-origin node {node_id!r} has no parents — incomplete provenance")
        result: set[str] = set()
        for parent_id in node.parent_ids:
            result |= self._find_origins(parent_id, visited)
        return result

    def analyze_independence(self, record_ids: list[str]) -> IndependenceResult:
        """
        Given record node_ids, determine how many independent origin nodes
        they trace back to — not how many datasets they are.
        """
        if not record_ids:
            return IndependenceResult(0, [], False, True, "no records provided")

        all_origins: set[str] = set()
        lineage_map: dict[str, str] = {}

        for rec_id in record_ids:
            try:
                origins = self._find_origins(rec_id, frozenset())
                all_origins |= origins
                # Map each record to its closest origin (first found)
                lineage_map[rec_id] = next(iter(origins)) if origins else "unknown"
            except KeyError as e:
                return IndependenceResult(0, [], False, True, f"missing node: {e}")
            except RecursionError as e:
                return IndependenceResult(0, [], False, True, str(e))
            except ValueError as e:
                return IndependenceResult(0, [], False, True, str(e))

        count = len(all_origins)
        origins_list = sorted(all_origins)

        if count == 0:
            return IndependenceResult(0, [], False, True, "no origin nodes found")

        is_indep = count > 1
        reason = (
            f"{count} independent origin(s): {origins_list}"
            if is_indep
            else f"all records share 1 origin ({origins_list[0]}) — not independent"
        )
        return IndependenceResult(count, origins_list, is_indep, False, reason, lineage_map)

    def verify_hashes(self, expected: dict[str, str]) -> bool:
        """Verify node content_hashes match expected (tamper detection)."""
        for node_id, exp_hash in expected.items():
            node = self._nodes.get(node_id)
            if node is None or node.content_hash != exp_hash:
                return False
        return True
