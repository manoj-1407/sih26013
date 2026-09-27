"""Conflict Detection Engine — Layer 5a.

Given a group of source records matched to the same canonical parcel,
identifies and classifies all conflicts across:
  - Geometry: BOUNDARY_OFFSET, AREA_MISMATCH, OVERLAP, GAP
  - Attributes: OWNER_REFERENCE_MISMATCH, LAND_USE_MISMATCH, etc.
  - Temporal: OUTDATED_SOURCE, CONCURRENT_CONFLICT
  - Provenance: SHARED_ORIGIN, UNKNOWN_LINEAGE
  - CRS: AXIS_ORDER, DATUM_MISMATCH, etc.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from itertools import combinations
from typing import Optional

from shapely.geometry import shape as shapely_shape

from app.core.geometry import compare_geometries
from app.core.crs_check import check_crs_plausibility
from app.core.temporal import analyze_temporal
from app.core.provenance import ProvenanceGraph
from app.ingestion.ingestor import IngestedRecord
from app.models.domain import ConflictType, ConflictSeverity


# ─────────────────────────────────────────────────────────────────────────────
# Severity thresholds (configurable per deployment)
# ─────────────────────────────────────────────────────────────────────────────

BOUNDARY_OFFSET_CRITICAL_M = 5.0       # >5m boundary offset → CRITICAL
BOUNDARY_OFFSET_HIGH_M = 2.0           # >2m → HIGH
BOUNDARY_OFFSET_MEDIUM_M = 0.5         # >0.5m → MEDIUM

AREA_MISMATCH_CRITICAL_PCT = 0.10      # >10% area diff → CRITICAL
AREA_MISMATCH_HIGH_PCT = 0.05          # >5% → HIGH
AREA_MISMATCH_MEDIUM_PCT = 0.02        # >2% → MEDIUM

OWNER_SIM_MISMATCH_THRESHOLD = 0.70    # below 70% similarity = mismatch

# Cross-layer conflict thresholds
BUILDING_OVERLAP_MIN_M2 = 1.0          # building outside parcel by > 1m²
UTILITY_CROSS_MIN_M = 0.5              # utility line crosses by > 0.5m


@dataclass
class DetectedConflict:
    conflict_id: str
    parcel_id: str
    conflict_type: ConflictType
    severity: ConflictSeverity
    record_ids: list[str]
    measure: Optional[float] = None
    measure_unit: Optional[str] = None
    description: str = ""
    evidence: dict = field(default_factory=dict)
    auto_resolvable: bool = False


def _geometry_severity(hausdorff_m: float, area_diff: float) -> ConflictSeverity:
    if hausdorff_m >= BOUNDARY_OFFSET_CRITICAL_M or area_diff >= AREA_MISMATCH_CRITICAL_PCT:
        return ConflictSeverity.CRITICAL
    if hausdorff_m >= BOUNDARY_OFFSET_HIGH_M or area_diff >= AREA_MISMATCH_HIGH_PCT:
        return ConflictSeverity.HIGH
    if hausdorff_m >= BOUNDARY_OFFSET_MEDIUM_M or area_diff >= AREA_MISMATCH_MEDIUM_PCT:
        return ConflictSeverity.MEDIUM
    return ConflictSeverity.LOW


def detect_geometry_conflicts(
    parcel_id: str,
    records: list[IngestedRecord],
) -> list[DetectedConflict]:
    """Detect pairwise geometry conflicts for records in a matched group."""
    conflicts: list[DetectedConflict] = []

    for rec_a, rec_b in combinations(records, 2):
        try:
            geom_a = shapely_shape(rec_a.geometry_geojson)
            geom_b = shapely_shape(rec_b.geometry_geojson)
        except Exception:
            continue

        cmp = compare_geometries(geom_a, geom_b)
        if not cmp.conflict:
            continue

        severity = _geometry_severity(
            cmp.hausdorff_m if cmp.hausdorff_m != float("inf") else 9999.0,
            cmp.area_ratio_diff,
        )

        # Choose most specific conflict type
        if cmp.conflict_type == "OVERLAP":
            ctype = ConflictType.OVERLAP
        elif cmp.conflict_type == "GAP":
            ctype = ConflictType.GAP
        elif cmp.area_ratio_diff > AREA_MISMATCH_MEDIUM_PCT and cmp.iou >= 0.95:
            ctype = ConflictType.AREA_MISMATCH
        else:
            ctype = ConflictType.BOUNDARY_OFFSET

        auto_resolvable = severity == ConflictSeverity.LOW

        conflicts.append(DetectedConflict(
            conflict_id=f"CONF-GEO-{uuid.uuid4().hex[:8].upper()}",
            parcel_id=parcel_id,
            conflict_type=ctype,
            severity=severity,
            record_ids=[rec_a.record_id, rec_b.record_id],
            measure=round(cmp.hausdorff_m, 2) if cmp.hausdorff_m != float("inf") else None,
            measure_unit="metres",
            description=(
                f"{ctype.value}: {rec_a.source_type.value} vs {rec_b.source_type.value}. "
                f"Boundary offset {cmp.hausdorff_m:.1f}m, area diff {cmp.area_ratio_diff:.1%}."
            ),
            evidence={
                "iou": cmp.iou,
                "hausdorff_m": cmp.hausdorff_m if cmp.hausdorff_m != float("inf") else None,
                "area_ratio_diff": cmp.area_ratio_diff,
                "centroid_dist_m": cmp.centroid_dist_m,
                "source_a": rec_a.source_type.value,
                "source_b": rec_b.source_type.value,
            },
            auto_resolvable=auto_resolvable,
        ))

    return conflicts


def detect_attribute_conflicts(
    parcel_id: str,
    records: list[IngestedRecord],
) -> list[DetectedConflict]:
    """Detect attribute conflicts across matched records."""
    conflicts: list[DetectedConflict] = []
    from rapidfuzz import fuzz

    for rec_a, rec_b in combinations(records, 2):
        attrs_a = rec_a.attributes_canonical
        attrs_b = rec_b.attributes_canonical

        # Owner reference mismatch
        owner_a = str(attrs_a.get("owner_reference", "")).strip()
        owner_b = str(attrs_b.get("owner_reference", "")).strip()
        if owner_a and owner_b:
            sim = fuzz.token_set_ratio(owner_a, owner_b) / 100.0
            if sim < OWNER_SIM_MISMATCH_THRESHOLD:
                conflicts.append(DetectedConflict(
                    conflict_id=f"CONF-ATTR-{uuid.uuid4().hex[:8].upper()}",
                    parcel_id=parcel_id,
                    conflict_type=ConflictType.OWNER_REFERENCE_MISMATCH,
                    severity=ConflictSeverity.MEDIUM,
                    record_ids=[rec_a.record_id, rec_b.record_id],
                    measure=round(sim * 100, 1),
                    measure_unit="similarity_pct",
                    description=(
                        f"Owner mismatch: '{owner_a}' ({rec_a.source_type.value}) vs "
                        f"'{owner_b}' ({rec_b.source_type.value}) — {sim:.0%} similar"
                    ),
                    evidence={"owner_a": owner_a, "owner_b": owner_b, "similarity": sim},
                    auto_resolvable=(sim >= 0.85),  # Transliteration variance
                ))

        # Land-use mismatch
        lu_a = str(attrs_a.get("land_use", "")).lower().strip()
        lu_b = str(attrs_b.get("land_use", "")).lower().strip()
        if lu_a and lu_b and lu_a != lu_b:
            conflicts.append(DetectedConflict(
                conflict_id=f"CONF-ATTR-{uuid.uuid4().hex[:8].upper()}",
                parcel_id=parcel_id,
                conflict_type=ConflictType.LAND_USE_MISMATCH,
                severity=ConflictSeverity.HIGH,
                record_ids=[rec_a.record_id, rec_b.record_id],
                description=(
                    f"Land-use mismatch: '{lu_a}' ({rec_a.source_type.value}) vs "
                    f"'{lu_b}' ({rec_b.source_type.value})"
                ),
                evidence={"land_use_a": lu_a, "land_use_b": lu_b},
                auto_resolvable=False,
            ))

        # Area attribute mismatch (when both have explicit area attributes)
        area_a = attrs_a.get("area_sqm_normalized")
        area_b = attrs_b.get("area_sqm_normalized")
        if area_a and area_b:
            try:
                diff_pct = abs(float(area_a) - float(area_b)) / max(float(area_a), float(area_b))
                if diff_pct > 0.03:  # >3% mismatch in stated area
                    conflicts.append(DetectedConflict(
                        conflict_id=f"CONF-ATTR-{uuid.uuid4().hex[:8].upper()}",
                        parcel_id=parcel_id,
                        conflict_type=ConflictType.AREA_ATTRIBUTE_MISMATCH,
                        severity=ConflictSeverity.MEDIUM if diff_pct < 0.10 else ConflictSeverity.HIGH,
                        record_ids=[rec_a.record_id, rec_b.record_id],
                        measure=round(diff_pct * 100, 2),
                        measure_unit="percent",
                        description=(
                            f"Stated area mismatch: {area_a:.1f}m² ({rec_a.source_type.value}) vs "
                            f"{area_b:.1f}m² ({rec_b.source_type.value}) — {diff_pct:.1%} difference"
                        ),
                        evidence={"area_a": area_a, "area_b": area_b, "diff_pct": diff_pct},
                        auto_resolvable=(diff_pct < 0.05),
                    ))
            except (TypeError, ValueError):
                pass

    return conflicts


def detect_provenance_conflicts(
    parcel_id: str,
    records: list[IngestedRecord],
    graph: Optional[ProvenanceGraph] = None,
) -> list[DetectedConflict]:
    """Detect provenance issues (shared origin, unknown lineage)."""
    conflicts: list[DetectedConflict] = []
    if graph is None:
        return conflicts

    prov_ids = [r.provenance_node_id for r in records if r.provenance_node_id]
    if len(prov_ids) < 2:
        if len(records) >= 2:
            conflicts.append(DetectedConflict(
                conflict_id=f"CONF-PROV-{uuid.uuid4().hex[:8].upper()}",
                parcel_id=parcel_id,
                conflict_type=ConflictType.UNKNOWN_LINEAGE,
                severity=ConflictSeverity.MEDIUM,
                record_ids=[r.record_id for r in records],
                description="Insufficient provenance information — source independence cannot be determined",
                auto_resolvable=False,
            ))
        return conflicts

    result = graph.analyze_independence(prov_ids)
    if result.unknown:
        conflicts.append(DetectedConflict(
            conflict_id=f"CONF-PROV-{uuid.uuid4().hex[:8].upper()}",
            parcel_id=parcel_id,
            conflict_type=ConflictType.UNKNOWN_LINEAGE,
            severity=ConflictSeverity.MEDIUM,
            record_ids=[r.record_id for r in records],
            description=f"Provenance unknown: {result.reason}",
            auto_resolvable=False,
        ))
    elif not result.is_independent:
        conflicts.append(DetectedConflict(
            conflict_id=f"CONF-PROV-{uuid.uuid4().hex[:8].upper()}",
            parcel_id=parcel_id,
            conflict_type=ConflictType.SHARED_ORIGIN,
            severity=ConflictSeverity.LOW,
            record_ids=[r.record_id for r in records],
            description=(
                f"Records share a common origin ({result.origins[0] if result.origins else 'unknown'}) "
                f"— they do not provide independent evidence"
            ),
            evidence={"independent_lineages": result.independent_lineages, "origins": result.origins},
            auto_resolvable=True,
        ))

    return conflicts


def detect_all_conflicts(
    parcel_id: str,
    records: list[IngestedRecord],
    graph: Optional[ProvenanceGraph] = None,
) -> list[DetectedConflict]:
    """Run all conflict detectors for a parcel group."""
    all_conflicts: list[DetectedConflict] = []
    all_conflicts.extend(detect_geometry_conflicts(parcel_id, records))
    all_conflicts.extend(detect_attribute_conflicts(parcel_id, records))
    all_conflicts.extend(detect_provenance_conflicts(parcel_id, records, graph))
    return all_conflicts
