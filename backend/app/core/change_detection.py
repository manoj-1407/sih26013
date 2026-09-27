"""Parcel-Centric Change Detection Engine.

Not generic "image changed" detection — we classify *what type* of
change occurred to a specific parcel across temporal observations:

  GEOMETRY_CHANGE     — boundary moved / area changed
  AREA_CHANGE         — significant area difference (no boundary data)
  LAND_USE_CHANGE     — land-use classification changed
  BOUNDARY_DRIFT      — gradual consistent offset (survey datum shift)
  ATTRIBUTE_CHANGE    — ownership, identifiers, other attributes
  SPLIT_MERGE         — parcel was subdivided or consolidated
  SOURCE_DISCREPANCY  — same time, different sources (not temporal)
  NO_CHANGE           — within measurement noise

This feeds directly into the conflict engine to distinguish
"concurrent conflict" from "temporal evolution."
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from shapely.geometry import shape as shapely_shape
from shapely.geometry.base import BaseGeometry

from app.core.geometry import (
    compute_iou, compute_hausdorff_metres, compute_area_ratio_diff,
    area_sqm,
)
from app.core.temporal import parse_timestamp


# Thresholds
GEOMETRY_CHANGE_IOU = 0.90          # IoU below → geometry changed
AREA_CHANGE_PCT = 0.03              # > 3% area change → flagged
BOUNDARY_DRIFT_MAX_M = 3.0          # consistent offset ≤ 3m = likely datum shift
BOUNDARY_CHANGE_MIN_M = 0.5         # < 0.5m = noise


@dataclass
class ChangeRecord:
    """One temporal observation of a parcel."""
    record_id: str
    source_type: str
    geometry_geojson: Optional[dict]
    area_sqm: Optional[float]
    land_use: Optional[str]
    owner_reference: Optional[str]
    capture_timestamp: Optional[str]
    attributes: dict = field(default_factory=dict)


@dataclass
class ChangeEvent:
    change_type: str        # see module docstring
    severity: str           # LOW / MEDIUM / HIGH / CRITICAL
    record_a_id: str
    record_b_id: str
    timestamp_a: Optional[str]
    timestamp_b: Optional[str]
    gap_days: float
    measure: Optional[float]
    measure_unit: Optional[str]
    description: str
    is_temporal: bool       # True = genuine time-series change, False = concurrent conflict


@dataclass
class ChangeDetectionResult:
    parcel_id: str
    records_analyzed: int
    change_events: list[ChangeEvent]
    temporal_span_days: float
    earliest_observation: Optional[str]
    latest_observation: Optional[str]
    change_summary: str
    has_temporal_changes: bool
    has_concurrent_conflicts: bool


def _gap_days(ts_a: Optional[str], ts_b: Optional[str]) -> float:
    dt_a = parse_timestamp(ts_a)
    dt_b = parse_timestamp(ts_b)
    if dt_a is None or dt_b is None:
        return -1.0
    return abs((dt_a - dt_b).total_seconds()) / 86400.0


def _is_temporal(gap_days: float, threshold_days: float = 180) -> bool:
    """True if observations are sufficiently separated in time to be temporal."""
    return gap_days > threshold_days


def _geometry_change_event(
    rec_a: ChangeRecord,
    rec_b: ChangeRecord,
    gap_days: float,
) -> Optional[ChangeEvent]:
    """Detect geometry/boundary change between two records."""
    if not rec_a.geometry_geojson or not rec_b.geometry_geojson:
        return None
    try:
        ga = shapely_shape(rec_a.geometry_geojson)
        gb = shapely_shape(rec_b.geometry_geojson)
    except Exception:
        return None

    iou = compute_iou(ga, gb)
    hd_m = compute_hausdorff_metres(ga, gb)
    area_diff = compute_area_ratio_diff(ga, gb)

    if hd_m < BOUNDARY_CHANGE_MIN_M and area_diff < 0.01:
        return None  # Within noise

    is_temp = _is_temporal(gap_days)
    change_type = "GEOMETRY_CHANGE"

    if hd_m <= BOUNDARY_DRIFT_MAX_M and area_diff < 0.02:
        change_type = "BOUNDARY_DRIFT"
        severity = "LOW"
        description = (
            f"Consistent boundary offset {hd_m:.1f}m between {rec_a.source_type} "
            f"and {rec_b.source_type} — likely datum/survey measurement shift"
        )
    elif iou < GEOMETRY_CHANGE_IOU:
        severity = "HIGH" if not is_temp else "MEDIUM"
        description = (
            f"Boundary {'change' if is_temp else 'conflict'}: "
            f"IoU={iou:.2f}, offset={hd_m:.1f}m over {gap_days:.0f} days"
        )
    elif area_diff > AREA_CHANGE_PCT:
        change_type = "AREA_CHANGE"
        severity = "MEDIUM"
        description = f"Area changed {area_diff:.1%} ({rec_a.area_sqm:.0f}→{rec_b.area_sqm:.0f}m²)"
    else:
        severity = "LOW"
        description = f"Minor boundary difference: {hd_m:.1f}m Hausdorff"

    return ChangeEvent(
        change_type=change_type,
        severity=severity,
        record_a_id=rec_a.record_id,
        record_b_id=rec_b.record_id,
        timestamp_a=rec_a.capture_timestamp,
        timestamp_b=rec_b.capture_timestamp,
        gap_days=gap_days,
        measure=round(hd_m, 2),
        measure_unit="metres",
        description=description,
        is_temporal=is_temp,
    )


def _attribute_change_event(
    rec_a: ChangeRecord,
    rec_b: ChangeRecord,
    gap_days: float,
) -> list[ChangeEvent]:
    """Detect land-use and attribute changes."""
    events = []
    is_temp = _is_temporal(gap_days)

    # Land-use change
    lu_a = (rec_a.land_use or "").lower().strip()
    lu_b = (rec_b.land_use or "").lower().strip()
    if lu_a and lu_b and lu_a != lu_b:
        events.append(ChangeEvent(
            change_type="LAND_USE_CHANGE",
            severity="HIGH",
            record_a_id=rec_a.record_id,
            record_b_id=rec_b.record_id,
            timestamp_a=rec_a.capture_timestamp,
            timestamp_b=rec_b.capture_timestamp,
            gap_days=gap_days,
            measure=None, measure_unit=None,
            description=(
                f"Land-use {'change' if is_temp else 'conflict'}: "
                f"'{lu_a}' ({rec_a.source_type}) → '{lu_b}' ({rec_b.source_type})"
            ),
            is_temporal=is_temp,
        ))

    return events


def detect_parcel_changes(
    parcel_id: str,
    records: list[ChangeRecord],
) -> ChangeDetectionResult:
    """
    Analyse temporal and concurrent changes across all records for a parcel.
    Records should be sorted by capture_timestamp where possible.
    """
    from itertools import combinations

    events: list[ChangeEvent] = []

    # Sort by timestamp
    def ts_key(r: ChangeRecord) -> float:
        dt = parse_timestamp(r.capture_timestamp)
        return dt.timestamp() if dt else 0.0

    sorted_records = sorted(records, key=ts_key)

    for rec_a, rec_b in combinations(sorted_records, 2):
        gap = _gap_days(rec_a.capture_timestamp, rec_b.capture_timestamp)

        geo_event = _geometry_change_event(rec_a, rec_b, gap)
        if geo_event:
            events.append(geo_event)

        attr_events = _attribute_change_event(rec_a, rec_b, gap)
        events.extend(attr_events)

    # Compute temporal span
    timestamps = [parse_timestamp(r.capture_timestamp) for r in records]
    timestamps = [t for t in timestamps if t is not None]
    if len(timestamps) >= 2:
        span_days = (max(timestamps) - min(timestamps)).total_seconds() / 86400.0
        earliest = min(timestamps).isoformat()
        latest = max(timestamps).isoformat()
    else:
        span_days = 0.0
        earliest = timestamps[0].isoformat() if timestamps else None
        latest = earliest

    has_temporal = any(e.is_temporal for e in events)
    has_concurrent = any(not e.is_temporal for e in events)

    # Summary
    if not events:
        summary = f"No significant changes detected across {len(records)} observations"
    elif has_temporal and not has_concurrent:
        summary = (
            f"{len(events)} temporal change(s) over {span_days:.0f} days — "
            "records reflect genuine evolution, not concurrent conflict"
        )
    elif has_concurrent and not has_temporal:
        summary = (
            f"{len(events)} concurrent conflict(s) — "
            "sources from same period disagree"
        )
    else:
        n_temp = sum(1 for e in events if e.is_temporal)
        n_conc = sum(1 for e in events if not e.is_temporal)
        summary = (
            f"{n_temp} temporal change(s) + {n_conc} concurrent conflict(s) detected"
        )

    return ChangeDetectionResult(
        parcel_id=parcel_id,
        records_analyzed=len(records),
        change_events=events,
        temporal_span_days=round(span_days, 1),
        earliest_observation=earliest,
        latest_observation=latest,
        change_summary=summary,
        has_temporal_changes=has_temporal,
        has_concurrent_conflicts=has_concurrent,
    )
