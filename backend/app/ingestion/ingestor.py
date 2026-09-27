"""Dataset Ingestor — Layer 1 of the harmonization pipeline.

Responsibilities:
  1. Accept GeoJSON FeatureCollection (or record list)
  2. Validate and repair geometries
  3. Normalize CRS to WGS84 (recording the transformation)
  4. Hash each source record (SHA-256, tamper detection)
  5. Apply schema normalization
  6. Profile data quality
  7. Write to DB as DBSourceRecord + DBDataset

Original data is never modified — we store both the original GeoJSON
and the normalized WKT alongside each other.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from shapely.geometry import mapping as shapely_mapping
from sqlalchemy.orm import Session

from app.core.geometry import validate_geojson_geometry, normalize_to_wgs84
from app.core.crs_check import check_crs_plausibility
from app.core.hashing import sha256_canonical
from app.core.provenance import ProvenanceGraph, ProvenanceNode
from app.ingestion.schema_normalizer import normalize_attributes
from app.ingestion.quality_profiler import profile_dataset
from app.models.database import DBDataset, DBSourceRecord, DBAuditEvent
from app.models.domain import SourceType, DataQualityLevel


@dataclass
class IngestedRecord:
    """Internal representation of a record that passed ingestion."""
    record_id: str
    source_type: SourceType
    dataset_id: str
    case_id: str
    geometry_wkt: str
    geometry_geojson: dict
    source_crs: str
    attributes_raw: dict
    attributes_canonical: dict
    capture_timestamp: Optional[str]
    provenance_node_id: Optional[str]
    content_hash: str
    bbox: tuple[float, float, float, float]
    centroid: tuple[float, float]
    area_sqm: Optional[float]
    quality_level: DataQualityLevel = DataQualityLevel.UNKNOWN


@dataclass
class RejectedRecord:
    original_id: Any
    reason: str
    field: str = ""


@dataclass
class IngestionResult:
    dataset_id: str
    case_id: str
    source_type: SourceType
    accepted: list[IngestedRecord] = field(default_factory=list)
    rejected: list[RejectedRecord] = field(default_factory=list)
    quality_profile: Any = None   # DataQualityProfile
    warnings: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.accepted) + len(self.rejected)

    @property
    def acceptance_rate(self) -> float:
        return len(self.accepted) / max(1, self.total)


def _extract_record_id(feature: dict, dataset_id: str, index: int) -> str:
    """Extract or generate a stable record ID."""
    props = feature.get("properties") or {}
    for candidate in ("id", "record_id", "parcel_id", "property_id", "khasra_no"):
        val = props.get(candidate)
        if val:
            return f"{dataset_id}::{str(val).strip()}"
    # Fallback: dataset + index
    return f"{dataset_id}::rec-{index:06d}"


def _flatten_coordinates(coords: Any, depth: int = 0) -> list:
    """Flatten coordinate arrays for pre-validation. Depth-limited."""
    if depth > 20 or not isinstance(coords, (list, tuple)):
        return []
    if not coords:
        return []
    if isinstance(coords[0], (int, float)):
        return [coords]
    result = []
    for item in coords:
        result.extend(_flatten_coordinates(item, depth + 1))
    return result


def ingest_dataset(
    case_id: str,
    source_type: SourceType,
    features: list[dict],
    source_crs: str = "EPSG:4326",
    label: str = "",
    authority: str = "",
    dataset_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> IngestionResult:
    """
    Ingest a list of GeoJSON-style feature dicts into a case.

    Each feature should have:
      - 'geometry': GeoJSON geometry dict
      - 'properties': attribute dict
      - optional 'id', 'capture_timestamp', 'provenance_node_id'
    """
    dataset_id = dataset_id or f"DS-{source_type.value[:3]}-{uuid.uuid4().hex[:8].upper()}"
    result = IngestionResult(
        dataset_id=dataset_id,
        case_id=case_id,
        source_type=source_type,
    )

    raw_records_for_profiler = []
    accepted: list[IngestedRecord] = []
    rejected: list[RejectedRecord] = []

    for i, feature in enumerate(features):
        rec_id = _extract_record_id(feature, dataset_id, i)
        props = feature.get("properties") or {}
        geom_dict = feature.get("geometry")
        capture_ts = (
            feature.get("capture_timestamp")
            or props.get("capture_date")
            or props.get("survey_date")
            or props.get("date")
        )
        prov_node_id = feature.get("provenance_node_id")

        raw_records_for_profiler.append({
            "geometry": geom_dict,
            "attributes": props,
            "capture_timestamp": capture_ts,
        })

        # Pre-validation: coordinate range check
        if geom_dict and isinstance(geom_dict, dict):
            coords = geom_dict.get("coordinates")
            if coords:
                flat = _flatten_coordinates(coords)
                if flat:
                    xs = [c[0] for c in flat if isinstance(c, (list, tuple)) and len(c) >= 2]
                    ys = [c[1] for c in flat if isinstance(c, (list, tuple)) and len(c) >= 2]
                    if xs and ys:
                        max_val = max(abs(v) for v in xs + ys)
                        if max_val > 1000:
                            rejected.append(RejectedRecord(
                                rec_id,
                                f"coordinate values ({max_val:.0f}) suggest projected metres mislabeled as degrees",
                                "coordinates",
                            ))
                            continue
                        if any(abs(y) > 90 for y in ys):
                            rejected.append(RejectedRecord(rec_id, "latitude outside [-90,90]", "geometry"))
                            continue

        # Geometry validation + repair
        vr = validate_geojson_geometry(geom_dict)
        if not vr.valid:
            rejected.append(RejectedRecord(rec_id, f"invalid geometry: {vr.reason}", "geometry"))
            continue

        # CRS normalization
        try:
            geom_wgs84 = normalize_to_wgs84(vr.geometry, source_crs)
        except Exception as e:
            rejected.append(RejectedRecord(rec_id, f"CRS normalization failed: {e}", "crs"))
            continue

        # Post-normalization CRS plausibility
        crs_result = check_crs_plausibility(geom_wgs84)
        if not crs_result.ok and crs_result.category in (
            "IMPOSSIBLE_EXTENT", "DEGREE_METRE_CONFUSION", "AXIS_ORDER"
        ):
            rejected.append(RejectedRecord(rec_id, f"CRS error: {crs_result.issue}", "crs"))
            continue

        # Schema normalization
        schema_result = normalize_attributes(props, source_type.value)
        canonical_attrs = schema_result.canonical

        # Content hash (canonical JSON of original attributes + geometry)
        content_hash = sha256_canonical({
            "geometry": geom_dict,
            "attributes": props,
            "source_crs": source_crs,
        }).hex_digest

        # Geometry metadata
        try:
            bbox = geom_wgs84.bounds
            centroid = (geom_wgs84.centroid.x, geom_wgs84.centroid.y)
        except Exception:
            bbox = (0.0, 0.0, 0.0, 0.0)
            centroid = (0.0, 0.0)

        area_sqm = schema_result.area_sqm
        if area_sqm is None:
            # Compute from geometry (approximate)
            from app.core.geometry import area_sqm as _area_sqm
            area_sqm = _area_sqm(geom_wgs84)

        # WKT for spatial storage
        try:
            wkt = geom_wgs84.wkt
        except Exception:
            wkt = ""

        ingested = IngestedRecord(
            record_id=rec_id,
            source_type=source_type,
            dataset_id=dataset_id,
            case_id=case_id,
            geometry_wkt=wkt,
            geometry_geojson=shapely_mapping(geom_wgs84),
            source_crs=source_crs,
            attributes_raw=props,
            attributes_canonical=canonical_attrs,
            capture_timestamp=str(capture_ts) if capture_ts else None,
            provenance_node_id=prov_node_id,
            content_hash=content_hash,
            bbox=bbox,
            centroid=centroid,
            area_sqm=area_sqm,
        )
        accepted.append(ingested)

    # Profile quality
    quality_profile = profile_dataset(
        dataset_id=dataset_id,
        source_type=source_type.value,
        records=raw_records_for_profiler,
    )

    result.accepted = accepted
    result.rejected = rejected
    result.quality_profile = quality_profile
    result.warnings = quality_profile.warnings

    # Persist to DB if session provided
    if db is not None:
        _persist_to_db(result, label, authority, db)

    return result


def _persist_to_db(result: IngestionResult, label: str, authority: str, db: Session) -> None:
    """Write dataset + records to database."""
    db_dataset = DBDataset(
        dataset_id=result.dataset_id,
        case_id=result.case_id,
        source_type=result.source_type.value,
        label=label,
        authority=authority,
        total_features=result.total,
        valid_features=len(result.accepted),
        quality_level=result.quality_profile.quality_level.value if result.quality_profile else "UNKNOWN",
        schema_fields=list(result.quality_profile.attribute_stats.completeness_by_field.keys())
        if result.quality_profile else [],
        profile=_profile_to_dict(result.quality_profile) if result.quality_profile else {},
    )
    db.merge(db_dataset)

    for rec in result.accepted:
        db_rec = DBSourceRecord(
            record_id=rec.record_id,
            dataset_id=rec.dataset_id,
            case_id=rec.case_id,
            source_type=rec.source_type.value,
            geometry_wkt=rec.geometry_wkt,
            geometry_geojson=rec.geometry_geojson,
            source_crs=rec.source_crs,
            attributes={**rec.attributes_raw, **{"_canonical": rec.attributes_canonical}},
            capture_timestamp=rec.capture_timestamp,
            provenance_node_id=rec.provenance_node_id,
            content_hash=rec.content_hash,
            quality_level=rec.quality_level.value,
            bbox_minx=rec.bbox[0],
            bbox_miny=rec.bbox[1],
            bbox_maxx=rec.bbox[2],
            bbox_maxy=rec.bbox[3],
            centroid_lon=rec.centroid[0],
            centroid_lat=rec.centroid[1],
            area_sqm=rec.area_sqm,
        )
        db.merge(db_rec)

    db.commit()


def _profile_to_dict(p) -> dict:
    """Convert DataQualityProfile to dict for JSON storage."""
    return {
        "quality_score": p.quality_score,
        "quality_level": p.quality_level.value,
        "total_features": p.total_features,
        "valid_geometries": p.geometry_stats.valid,
        "invalid_geometries": p.geometry_stats.invalid_unfixable,
        "repaired_geometries": p.geometry_stats.repaired,
        "validity_rate": p.geometry_stats.validity_rate,
        "duplicate_ids": p.attribute_stats.duplicate_ids,
        "missing_timestamps": p.missing_timestamps,
        "crs_issues": p.crs_issues,
        "area_outliers": p.attribute_stats.area_outliers,
        "area_stats": p.attribute_stats.area_stats,
        "warnings": p.warnings,
    }
