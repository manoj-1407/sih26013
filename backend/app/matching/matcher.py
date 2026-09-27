"""Multi-Signal Parcel Matching Engine — Layer 4.

Matches source records to canonical parcels using a weighted
multi-signal approach:
  - Geometry: IoU, Hausdorff, area ratio, centroid distance
  - Identifiers: exact + normalized match on parcel/khasra/ulpin
  - Attributes: owner name fuzzy similarity, land-use match
  - Topology: same neighbors (future)
  - Provenance: independent lineage count

Philosophy:
  AI proposes candidates → deterministic rules score them → 
  provenance weights independence → hard constraints can block.
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz
from shapely.geometry import shape as shapely_shape

from app.core.geometry import (
    compute_iou, compute_hausdorff_metres,
    compute_centroid_dist_metres, compute_area_ratio_diff,
)
from app.core.spatial_index import SpatialCandidateIndex, IndexedRecord
from app.core.provenance import ProvenanceGraph
from app.core.temporal import analyze_temporal
from app.ingestion.ingestor import IngestedRecord


# ─────────────────────────────────────────────────────────────────────────────
# Match score components (all 0-1)
# ─────────────────────────────────────────────────────────────────────────────

WEIGHTS = {
    "geometry": 0.35,
    "identifier": 0.25,
    "attributes": 0.15,
    "temporal": 0.10,
    "provenance": 0.15,
}

# Minimum score thresholds
MATCH_THRESHOLD = 0.60       # below → no match
REVIEW_THRESHOLD = 0.75      # below → review required, above → candidate match
HIGH_CONF_THRESHOLD = 0.88   # above → high confidence match


@dataclass
class MatchEvidence:
    geometry_score: float = 0.0
    identifier_score: float = 0.0
    attribute_score: float = 0.0
    temporal_score: float = 0.0
    provenance_score: float = 0.0
    overall_score: float = 0.0
    # Details
    iou: Optional[float] = None
    hausdorff_m: Optional[float] = None
    area_ratio_diff: Optional[float] = None
    centroid_dist_m: Optional[float] = None
    identifier_match_type: str = "none"   # exact / normalized / none
    matched_identifier: Optional[str] = None
    owner_similarity: Optional[float] = None
    land_use_match: bool = False
    temporal_gap_days: float = -1
    independent_lineages: int = 0
    explanation: list[str] = field(default_factory=list)


@dataclass
class MatchPair:
    record_id_a: str
    record_id_b: str
    evidence: MatchEvidence
    is_match: bool
    requires_review: bool
    match_method: str = "MULTI_SIGNAL"


def _normalize_identifier(val: Optional[str]) -> Optional[str]:
    """Normalize parcel identifier: lowercase, strip spaces/punctuation, NFKD."""
    if not val:
        return None
    val = unicodedata.normalize("NFKD", str(val))
    val = re.sub(r"[^a-z0-9]", "", val.lower())
    return val or None


def _score_geometry(rec_a: IngestedRecord, rec_b: IngestedRecord) -> tuple[float, dict]:
    """Score geometry similarity 0-1."""
    try:
        geom_a = shapely_shape(rec_a.geometry_geojson)
        geom_b = shapely_shape(rec_b.geometry_geojson)
    except Exception:
        return 0.0, {}

    iou = compute_iou(geom_a, geom_b)
    hausdorff_m = compute_hausdorff_metres(geom_a, geom_b)
    area_diff = compute_area_ratio_diff(geom_a, geom_b)
    centroid_m = compute_centroid_dist_metres(geom_a, geom_b)

    # IoU score (0-1, inverted if no polygon)
    iou_score = max(0.0, iou) if iou >= 0 else 0.0

    # Hausdorff score: 0 at 500m+, 1 at 0m
    hd_score = max(0.0, 1.0 - hausdorff_m / 500.0) if hausdorff_m != float("inf") else 0.0

    # Area score: 1 at 0 diff, 0 at 100% diff
    area_score = max(0.0, 1.0 - area_diff)

    # Centroid score: 1 at 0m, 0 at 500m+
    cent_score = max(0.0, 1.0 - centroid_m / 500.0) if centroid_m != float("inf") else 0.0

    composite = (iou_score * 0.4 + hd_score * 0.3 + area_score * 0.2 + cent_score * 0.1)
    return composite, {
        "iou": round(iou, 4) if iou >= 0 else None,
        "hausdorff_m": round(hausdorff_m, 2) if hausdorff_m != float("inf") else None,
        "area_ratio_diff": round(area_diff, 4),
        "centroid_dist_m": round(centroid_m, 2) if centroid_m != float("inf") else None,
    }


def _score_identifiers(rec_a: IngestedRecord, rec_b: IngestedRecord) -> tuple[float, str, Optional[str]]:
    """Score identifier overlap 0-1. Returns (score, match_type, matched_value)."""
    id_fields = ("parcel_reference", "ulpin", "survey_number")
    attrs_a = rec_a.attributes_canonical
    attrs_b = rec_b.attributes_canonical

    # Exact match on any canonical ID field
    for f in id_fields:
        val_a = attrs_a.get(f)
        val_b = attrs_b.get(f)
        if val_a and val_b and str(val_a).strip() == str(val_b).strip():
            return 1.0, "exact", str(val_a)

    # Normalized match
    for f in id_fields:
        n_a = _normalize_identifier(attrs_a.get(f))
        n_b = _normalize_identifier(attrs_b.get(f))
        if n_a and n_b and n_a == n_b:
            return 0.9, "normalized", n_a

    # Partial match (one is substring of other)
    for f in id_fields:
        n_a = _normalize_identifier(attrs_a.get(f))
        n_b = _normalize_identifier(attrs_b.get(f))
        if n_a and n_b:
            if n_a in n_b or n_b in n_a:
                return 0.6, "partial", f"{n_a}/{n_b}"

    return 0.0, "none", None


def _score_attributes(rec_a: IngestedRecord, rec_b: IngestedRecord) -> tuple[float, dict]:
    """Score attribute similarity 0-1."""
    attrs_a = rec_a.attributes_canonical
    attrs_b = rec_b.attributes_canonical

    scores = []
    details = {}

    # Owner name similarity
    owner_a = attrs_a.get("owner_reference")
    owner_b = attrs_b.get("owner_reference")
    if owner_a and owner_b:
        sim = fuzz.token_set_ratio(str(owner_a), str(owner_b)) / 100.0
        scores.append(sim)
        details["owner_similarity"] = round(sim, 3)
    else:
        details["owner_similarity"] = None

    # Land-use match
    lu_a = str(attrs_a.get("land_use", "")).lower().strip()
    lu_b = str(attrs_b.get("land_use", "")).lower().strip()
    if lu_a and lu_b:
        lu_match = lu_a == lu_b
        scores.append(1.0 if lu_match else 0.2)
        details["land_use_match"] = lu_match
    else:
        details["land_use_match"] = None

    # Ward match
    ward_a = str(attrs_a.get("ward", "")).lower().strip()
    ward_b = str(attrs_b.get("ward", "")).lower().strip()
    if ward_a and ward_b:
        scores.append(1.0 if ward_a == ward_b else 0.0)
        details["ward_match"] = ward_a == ward_b

    return (sum(scores) / max(1, len(scores))) if scores else 0.5, details


def _score_temporal(rec_a: IngestedRecord, rec_b: IngestedRecord) -> tuple[float, float]:
    """Score temporal consistency 0-1. Recent + concurrent = high score."""
    temp = analyze_temporal(rec_a.capture_timestamp, rec_b.capture_timestamp)
    if not temp.valid:
        return 0.7, -1  # neutral on missing timestamps
    # Qualified means large gap — lower confidence they describe same state
    if temp.qualified:
        return 0.4, temp.gap_days
    return 0.9, temp.gap_days


def _score_provenance(
    rec_a: IngestedRecord,
    rec_b: IngestedRecord,
    graph: Optional[ProvenanceGraph],
) -> tuple[float, int]:
    """Score provenance independence 0-1. Independent sources = higher evidence quality."""
    if graph is None:
        return 0.5, 0  # neutral

    prov_ids = []
    if rec_a.provenance_node_id:
        prov_ids.append(rec_a.provenance_node_id)
    if rec_b.provenance_node_id:
        prov_ids.append(rec_b.provenance_node_id)

    if len(prov_ids) < 2:
        return 0.5, 0

    result = graph.analyze_independence(prov_ids)
    if result.unknown:
        return 0.5, 0
    if result.is_independent:
        return min(1.0, 0.7 + 0.1 * result.independent_lineages), result.independent_lineages
    # Shared origin: both records trace to same source — lower evidence value
    return 0.3, result.independent_lineages


def compute_match_score(
    rec_a: IngestedRecord,
    rec_b: IngestedRecord,
    graph: Optional[ProvenanceGraph] = None,
) -> MatchEvidence:
    """Compute full multi-signal match score between two ingested records."""
    geo_score, geo_details = _score_geometry(rec_a, rec_b)
    id_score, id_type, id_val = _score_identifiers(rec_a, rec_b)
    attr_score, attr_details = _score_attributes(rec_a, rec_b)
    temp_score, gap_days = _score_temporal(rec_a, rec_b)
    prov_score, n_lineages = _score_provenance(rec_a, rec_b, graph)

    overall = (
        geo_score * WEIGHTS["geometry"]
        + id_score * WEIGHTS["identifier"]
        + attr_score * WEIGHTS["attributes"]
        + temp_score * WEIGHTS["temporal"]
        + prov_score * WEIGHTS["provenance"]
    )

    explanation = []
    if geo_score > 0.8:
        explanation.append(f"Strong geometry match (IoU={geo_details.get('iou', 'N/A')})")
    elif geo_score < 0.4:
        explanation.append(f"Weak geometry match ({geo_details.get('hausdorff_m', '?')}m boundary offset)")
    if id_type != "none":
        explanation.append(f"Identifier {id_type} match: {id_val}")
    if attr_details.get("owner_similarity"):
        explanation.append(f"Owner name similarity: {attr_details['owner_similarity']:.0%}")
    if gap_days > 0:
        explanation.append(f"Temporal gap: {gap_days:.0f} days")
    if n_lineages > 1:
        explanation.append(f"{n_lineages} independent source lineages")

    return MatchEvidence(
        geometry_score=round(geo_score, 4),
        identifier_score=round(id_score, 4),
        attribute_score=round(attr_score, 4),
        temporal_score=round(temp_score, 4),
        provenance_score=round(prov_score, 4),
        overall_score=round(overall, 4),
        iou=geo_details.get("iou"),
        hausdorff_m=geo_details.get("hausdorff_m"),
        area_ratio_diff=geo_details.get("area_ratio_diff"),
        centroid_dist_m=geo_details.get("centroid_dist_m"),
        identifier_match_type=id_type,
        matched_identifier=id_val,
        owner_similarity=attr_details.get("owner_similarity"),
        land_use_match=bool(attr_details.get("land_use_match")),
        temporal_gap_days=gap_days,
        independent_lineages=n_lineages,
        explanation=explanation,
    )


class ParcelMatcher:
    """
    Orchestrates candidate generation and scoring across all source records.
    Produces groups of records that likely describe the same parcel.
    """

    def __init__(self, graph: Optional[ProvenanceGraph] = None):
        self._graph = graph
        self._index = SpatialCandidateIndex()
        self._records: dict[str, IngestedRecord] = {}

    def add_record(self, record: IngestedRecord) -> None:
        """Add a record to the index."""
        from shapely.geometry import shape as s
        try:
            geom = s(record.geometry_geojson)
        except Exception:
            return
        self._records[record.record_id] = record
        if record.record_id not in self._index:
            self._index.insert(record.record_id, geom)

    def run_matching(self) -> list[MatchPair]:
        """Generate all candidate pairs and score them."""
        pairs: list[MatchPair] = []
        from shapely.geometry import shape as s

        indexed = [
            r for r in self._index._records.values()
        ]

        for rec_a_idx, rec_b_idx in self._index.generate_candidate_pairs(indexed):
            rec_a = self._records.get(rec_a_idx.record_id)
            rec_b = self._records.get(rec_b_idx.record_id)
            if rec_a is None or rec_b is None:
                continue

            evidence = compute_match_score(rec_a, rec_b, self._graph)
            is_match = evidence.overall_score >= MATCH_THRESHOLD
            requires_review = is_match and evidence.overall_score < REVIEW_THRESHOLD

            pairs.append(MatchPair(
                record_id_a=rec_a.record_id,
                record_id_b=rec_b.record_id,
                evidence=evidence,
                is_match=is_match,
                requires_review=requires_review,
            ))

        return pairs

    def group_into_parcels(self, pairs: list[MatchPair]) -> list[list[str]]:
        """
        Union-Find grouping: each connected component of matched records
        becomes one canonical parcel.
        """
        parent: dict[str, str] = {rid: rid for rid in self._records}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for pair in pairs:
            if pair.is_match:
                if pair.record_id_a in parent and pair.record_id_b in parent:
                    union(pair.record_id_a, pair.record_id_b)

        # Collect groups
        groups: dict[str, list[str]] = {}
        for rid in self._records:
            root = find(rid)
            groups.setdefault(root, []).append(rid)

        return list(groups.values())
