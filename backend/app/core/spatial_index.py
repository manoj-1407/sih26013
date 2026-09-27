"""R-tree spatial candidate index for fast parcel proximity lookup.

The index provides false-negative-free candidate generation:
every potential conflict pair passes through, no pair is missed.
The buffer expansion ensures nearby records are always captured.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterator

from rtree import index as rtree_index
from shapely.geometry.base import BaseGeometry


# ~1 km buffer in geographic degrees (conservative, avoids false negatives)
CANDIDATE_BUFFER_DEGREES = 0.01


@dataclass
class IndexedRecord:
    record_id: str
    geometry: BaseGeometry
    bounds: tuple[float, float, float, float]
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class SpatialCandidateIndex:
    """R-tree index for spatial candidate filtering."""

    def __init__(self):
        self._idx = rtree_index.Index()
        self._records: dict[int, IndexedRecord] = {}
        self._id_map: dict[str, int] = {}   # record_id → int id
        self._counter = 0

    def insert(self, record_id: str, geometry: BaseGeometry, metadata: dict = None) -> None:
        if record_id in self._id_map:
            raise ValueError(f"Record {record_id!r} already in index")
        iid = self._counter
        self._counter += 1
        self._id_map[record_id] = iid
        bounds = geometry.bounds
        self._idx.insert(iid, bounds)
        self._records[iid] = IndexedRecord(record_id, geometry, bounds, metadata or {})

    def remove(self, record_id: str) -> None:
        if record_id not in self._id_map:
            return
        iid = self._id_map.pop(record_id)
        rec = self._records.pop(iid, None)
        if rec:
            self._idx.delete(iid, rec.bounds)

    def query_candidates(
        self,
        geometry: BaseGeometry,
        buffer_degrees: float = CANDIDATE_BUFFER_DEGREES,
    ) -> list[IndexedRecord]:
        """All indexed records whose bboxes intersect buffered bbox."""
        minx, miny, maxx, maxy = geometry.bounds
        buffered = (
            minx - buffer_degrees,
            miny - buffer_degrees,
            maxx + buffer_degrees,
            maxy + buffer_degrees,
        )
        return [self._records[iid] for iid in self._idx.intersection(buffered)]

    def generate_candidate_pairs(
        self,
        records: list[IndexedRecord],
        buffer_degrees: float = CANDIDATE_BUFFER_DEGREES,
    ) -> Iterator[tuple[IndexedRecord, IndexedRecord]]:
        """Generate unique (a, b) pairs where a.record_id < b.record_id."""
        seen: set[tuple[int, int]] = set()
        for rec in records:
            for cand in self.query_candidates(rec.geometry, buffer_degrees):
                if cand.record_id == rec.record_id:
                    continue
                key = tuple(sorted([self._id_map[rec.record_id], self._id_map[cand.record_id]]))
                if key not in seen:
                    seen.add(key)
                    a_iid, b_iid = key
                    yield self._records[a_iid], self._records[b_iid]

    def query_within_metres(
        self,
        geometry: BaseGeometry,
        metres: float,
    ) -> list[IndexedRecord]:
        """Query with a specific metre-based buffer (approximate)."""
        # 1 degree ≈ 111km, so metres / 111000 = degrees
        buffer_deg = metres / 111000.0
        return self.query_candidates(geometry, buffer_degrees=buffer_deg)

    def __len__(self) -> int:
        return len(self._records)

    def __contains__(self, record_id: str) -> bool:
        return record_id in self._id_map
