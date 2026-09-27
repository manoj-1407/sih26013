"""Data Quality Profiler — ISO 19157-informed quality assessment.

For every ingested dataset, produces a DataQualityProfile covering:
  - Geometry validity rate
  - CRS completeness
  - Attribute completeness
  - Duplicate detection
  - Temporal coverage
  - Area outlier detection

This gates the ingestion pipeline: low-quality data gets a warning tag,
not silent acceptance.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any
import statistics

from shapely.geometry import shape as shapely_shape
from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid

from app.core.crs_check import check_crs_plausibility
from app.models.domain import DataQualityLevel


@dataclass
class GeometryQualityStats:
    total: int = 0
    valid: int = 0
    repaired: int = 0
    invalid_unfixable: int = 0
    empty: int = 0
    self_intersecting: int = 0
    validity_rate: float = 0.0


@dataclass
class AttributeQualityStats:
    total_records: int = 0
    missing_by_field: dict[str, int] = field(default_factory=dict)
    completeness_by_field: dict[str, float] = field(default_factory=dict)
    duplicate_ids: int = 0
    area_outliers: int = 0
    area_stats: dict = field(default_factory=dict)


@dataclass
class DataQualityProfile:
    dataset_id: str
    source_type: str
    total_features: int = 0
    geometry_stats: GeometryQualityStats = field(default_factory=GeometryQualityStats)
    attribute_stats: AttributeQualityStats = field(default_factory=AttributeQualityStats)
    crs_issues: int = 0
    missing_timestamps: int = 0
    quality_level: DataQualityLevel = DataQualityLevel.UNKNOWN
    quality_score: float = 0.0   # 0-100
    warnings: list[str] = field(default_factory=list)


def _try_parse_geometry(geom_dict: Any) -> tuple[Optional[BaseGeometry], str]:
    """Returns (geometry or None, status)."""
    if not isinstance(geom_dict, dict):
        return None, "not_a_dict"
    try:
        geom = shapely_shape(geom_dict)
    except Exception:
        return None, "parse_error"
    if geom.is_empty:
        return None, "empty"
    if not geom.is_valid:
        fixed = make_valid(geom)
        if fixed.is_empty:
            return None, "invalid_unfixable"
        return fixed, "repaired"
    return geom, "valid"


def profile_dataset(
    dataset_id: str,
    source_type: str,
    records: list[dict],
    id_field: Optional[str] = None,
    area_field: Optional[str] = None,
) -> DataQualityProfile:
    """
    Profile a list of raw records (each a dict with optional 'geometry', 'attributes', 'timestamp').
    Returns a DataQualityProfile.
    """
    profile = DataQualityProfile(
        dataset_id=dataset_id,
        source_type=source_type,
        total_features=len(records),
    )
    geo_stats = GeometryQualityStats(total=len(records))
    attr_stats = AttributeQualityStats(total_records=len(records))
    warnings: list[str] = []

    seen_ids: dict[str, int] = {}
    area_values: list[float] = []

    all_attr_keys: set[str] = set()
    missing_by_field: dict[str, int] = {}
    missing_timestamps = 0
    crs_issues = 0

    for rec in records:
        # Geometry quality
        geom_dict = rec.get("geometry")
        if geom_dict:
            geom, status = _try_parse_geometry(geom_dict)
            if status == "valid":
                geo_stats.valid += 1
                crs_info = check_crs_plausibility(geom)
                if not crs_info.ok:
                    crs_issues += 1
            elif status == "repaired":
                geo_stats.valid += 1
                geo_stats.repaired += 1
            elif status == "empty":
                geo_stats.empty += 1
            elif status == "invalid_unfixable":
                geo_stats.invalid_unfixable += 1
        else:
            geo_stats.invalid_unfixable += 1

        # Timestamp
        if not rec.get("capture_timestamp") and not rec.get("timestamp"):
            missing_timestamps += 1

        # Attributes
        attrs = rec.get("attributes", {}) or {}
        all_attr_keys.update(attrs.keys())
        for k in all_attr_keys:
            if not attrs.get(k):
                missing_by_field[k] = missing_by_field.get(k, 0) + 1

        # Duplicate ID check
        if id_field:
            rec_id = attrs.get(id_field)
            if rec_id:
                seen_ids[rec_id] = seen_ids.get(rec_id, 0) + 1

        # Area values for outlier detection
        if area_field:
            val = attrs.get(area_field)
            if val is not None:
                try:
                    area_values.append(float(val))
                except (ValueError, TypeError):
                    pass

    geo_stats.invalid_unfixable = max(0, geo_stats.total - geo_stats.valid - geo_stats.empty)
    geo_stats.validity_rate = (geo_stats.valid / max(1, geo_stats.total)) * 100.0

    # Attribute completeness
    total = max(1, len(records))
    completeness: dict[str, float] = {}
    for k in all_attr_keys:
        missing = missing_by_field.get(k, 0)
        completeness[k] = round((1 - missing / total) * 100, 1)

    attr_stats.missing_by_field = missing_by_field
    attr_stats.completeness_by_field = completeness
    attr_stats.duplicate_ids = sum(1 for v in seen_ids.values() if v > 1)

    # Area outlier detection (IQR method)
    outliers = 0
    area_stats: dict = {}
    if len(area_values) >= 4:
        q1 = sorted(area_values)[len(area_values) // 4]
        q3 = sorted(area_values)[3 * len(area_values) // 4]
        iqr = q3 - q1
        lower = q1 - 3 * iqr
        upper = q3 + 3 * iqr
        outliers = sum(1 for a in area_values if a < lower or a > upper)
        area_stats = {
            "min": round(min(area_values), 2),
            "max": round(max(area_values), 2),
            "median": round(statistics.median(area_values), 2),
            "q1": round(q1, 2), "q3": round(q3, 2),
            "outliers": outliers,
        }
    attr_stats.area_outliers = outliers
    attr_stats.area_stats = area_stats

    # Warnings
    if geo_stats.validity_rate < 90:
        warnings.append(f"Geometry validity rate {geo_stats.validity_rate:.1f}% is below 90%")
    if attr_stats.duplicate_ids > 0:
        warnings.append(f"{attr_stats.duplicate_ids} duplicate parcel IDs detected")
    if crs_issues > 0:
        warnings.append(f"{crs_issues} records have CRS plausibility issues")
    if missing_timestamps > len(records) * 0.2:
        warnings.append(f"{missing_timestamps}/{len(records)} records missing timestamps")
    if outliers > 0:
        warnings.append(f"{outliers} area outliers detected (possible data errors)")

    # Quality score (0–100)
    geo_score = geo_stats.validity_rate
    ts_score = max(0.0, 100.0 - (missing_timestamps / max(1, len(records))) * 100)
    dup_score = max(0.0, 100.0 - (attr_stats.duplicate_ids / max(1, len(records))) * 100)
    quality_score = (geo_score * 0.5 + ts_score * 0.25 + dup_score * 0.25)

    quality_level = (
        DataQualityLevel.HIGH if quality_score >= 90
        else DataQualityLevel.MEDIUM if quality_score >= 70
        else DataQualityLevel.LOW
    )

    profile.geometry_stats = geo_stats
    profile.attribute_stats = attr_stats
    profile.crs_issues = crs_issues
    profile.missing_timestamps = missing_timestamps
    profile.quality_level = quality_level
    profile.quality_score = round(quality_score, 1)
    profile.warnings = warnings

    return profile
