"""Imagery-Derived Feature Adapter — P0 Gap vs. THINK TWICE / A.L.I.G.N.

This module consumes pre-extracted geospatial features derived from
drone ORI, orthophotos, or satellite imagery and treats them as
evidence sources in the harmonization pipeline.

We do NOT rebuild YOLOv11-seg or SAM-2 (that is SIH26012 territory).
Instead, we accept the OUTPUT of such systems — GeoJSON building footprints,
detected parcel boundaries, road edges — as evidence layers.

Supported input types:
  1. Building footprints (GeoJSON) — from drone/satellite extraction
  2. Extracted parcel boundaries (GeoJSON) — from AI segmentation
  3. Road/utility centerlines (GeoJSON) — from feature extraction
  4. ORI extent + metadata (GeoTIFF) — spatial coverage + accuracy metadata

For each input, we:
  a) Validate and normalize geometry
  b) Assign a source quality weight based on imagery metadata
  c) Create a provenance node marking it as "imagery-derived"
  d) Feed into the standard ingestor pipeline

Why this architecture:
  Treats AI-extracted features as evidence, not as the authoritative answer.
  AI proposes. Ground rules constrain. Human approves.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

from app.ingestion.format_adapters import from_geojson, from_geotiff_metadata


# Quality weights based on imagery source
IMAGERY_QUALITY_WEIGHTS = {
    "gnss_rtk": 1.00,        # GNSS RTK ground survey — highest
    "drone_ori": 0.92,        # Drone ORI (< 5cm GSD)
    "uav_photogrammetry": 0.88,
    "satellite_high_res": 0.80,  # < 50cm GSD
    "satellite_medium_res": 0.65,  # 50cm–2m GSD
    "satellite_low_res": 0.45,
    "aerial_photo": 0.75,
    "historical_survey": 0.55,
    "unknown": 0.50,
}


@dataclass
class ImagerySourceMetadata:
    """Metadata about the imagery source that features were derived from."""
    imagery_type: str               # "drone_ori", "satellite_high_res", etc.
    gsd_cm: Optional[float]         # Ground sampling distance in cm
    acquisition_date: Optional[str]
    accuracy_m: Optional[float]     # Horizontal positional accuracy
    provider: str = "unknown"
    flight_height_m: Optional[float] = None
    overlap_pct: Optional[float] = None
    sensor: str = "unknown"
    quality_weight: float = 0.50


def _infer_imagery_type(metadata: dict) -> str:
    """Infer imagery type from metadata dict."""
    height = metadata.get("flight_height_m") or metadata.get("Flight_Height_m")
    gsd = metadata.get("gsd_cm") or metadata.get("GSD_cm")
    provider = str(metadata.get("provider", "") or metadata.get("source", "")).lower()

    if "drone" in provider or "uav" in provider or (height and float(height) < 500):
        return "drone_ori"
    if "satellite" in provider:
        if gsd and float(gsd) < 50:
            return "satellite_high_res"
        return "satellite_medium_res"
    if "aerial" in provider:
        return "aerial_photo"
    return "unknown"


@dataclass
class DerivedFeatureSet:
    """
    A set of features extracted from imagery, ready for ingestor pipeline.
    """
    feature_type: str           # "building_footprint", "parcel_boundary", "road_edge", "utility"
    features: list[dict]        # canonical feature dicts
    source_metadata: ImagerySourceMetadata
    provenance_nodes: list[dict]  # nodes to register in provenance graph
    quality_weight: float
    evidence_note: str


def adapt_building_footprints(
    geojson_data: str | bytes | dict,
    imagery_metadata: Optional[dict] = None,
) -> DerivedFeatureSet:
    """
    Adapt AI-extracted building footprints from imagery into evidence features.
    
    These become BUILDING_FOOTPRINT source records in the canonical model,
    used for:
      - cross-layer topology validation (building outside parcel?)
      - parcel boundary evidence corroboration
      - encroachment detection
    """
    features = from_geojson(geojson_data)
    meta = imagery_metadata or {}

    imagery_type = _infer_imagery_type(meta)
    gsd = meta.get("gsd_cm")
    acq_date = meta.get("acquisition_date") or meta.get("date")
    accuracy = meta.get("accuracy_m") or (float(gsd) / 100.0 * 2 if gsd else None)
    height = meta.get("flight_height_m")

    src_meta = ImagerySourceMetadata(
        imagery_type=imagery_type,
        gsd_cm=float(gsd) if gsd else None,
        acquisition_date=str(acq_date) if acq_date else None,
        accuracy_m=float(accuracy) if accuracy else None,
        provider=meta.get("provider", "unknown"),
        flight_height_m=float(height) if height else None,
        quality_weight=IMAGERY_QUALITY_WEIGHTS.get(imagery_type, 0.50),
    )

    # Tag each feature with imagery provenance
    prov_origin_id = f"ORIG-IMAGERY-{uuid.uuid4().hex[:8].upper()}"
    prov_ds_id = f"DS-IMAGERY-BLD-{uuid.uuid4().hex[:8].upper()}"

    for f in features:
        f["provenance_node_id"] = prov_ds_id
        f.setdefault("capture_timestamp", acq_date)
        props = f.get("properties", {})
        props["imagery_type"] = imagery_type
        props["gsd_cm"] = str(gsd) if gsd else "unknown"
        props["accuracy_m"] = str(accuracy) if accuracy else "unknown"
        props["derived_from"] = "imagery_extraction"

    prov_nodes = [
        {
            "node_id": prov_origin_id,
            "node_type": "origin",
            "parent_ids": [],
            "label": f"Imagery source: {imagery_type} ({acq_date or 'date unknown'})",
        },
        {
            "node_id": prov_ds_id,
            "node_type": "dataset",
            "parent_ids": [prov_origin_id],
            "label": f"AI-extracted building footprints from {imagery_type}",
        },
    ]

    return DerivedFeatureSet(
        feature_type="building_footprint",
        features=features,
        source_metadata=src_meta,
        provenance_nodes=prov_nodes,
        quality_weight=src_meta.quality_weight,
        evidence_note=(
            f"Building footprints extracted from {imagery_type} "
            f"({src_meta.quality_weight:.0%} quality weight). "
            "Used as cross-layer topology evidence, not as authoritative parcel boundary."
        ),
    )


def adapt_extracted_boundaries(
    geojson_data: str | bytes | dict,
    imagery_metadata: Optional[dict] = None,
) -> DerivedFeatureSet:
    """
    Adapt AI-extracted parcel boundaries from imagery.
    These feed into the matching engine as DRONE_ORI source records.
    """
    features = from_geojson(geojson_data)
    meta = imagery_metadata or {}
    imagery_type = _infer_imagery_type(meta)
    acq_date = meta.get("acquisition_date") or meta.get("date")
    gsd = meta.get("gsd_cm")
    accuracy = meta.get("accuracy_m") or (float(gsd) / 100.0 * 1.5 if gsd else None)

    src_meta = ImagerySourceMetadata(
        imagery_type=imagery_type,
        gsd_cm=float(gsd) if gsd else None,
        acquisition_date=str(acq_date) if acq_date else None,
        accuracy_m=float(accuracy) if accuracy else None,
        quality_weight=IMAGERY_QUALITY_WEIGHTS.get(imagery_type, 0.50),
    )

    prov_origin_id = f"ORIG-IMAGERY-{uuid.uuid4().hex[:8].upper()}"
    prov_ds_id = f"DS-IMAGERY-PARCEL-{uuid.uuid4().hex[:8].upper()}"

    for f in features:
        f["provenance_node_id"] = prov_ds_id
        f.setdefault("capture_timestamp", acq_date)
        props = f.get("properties", {})
        props["imagery_type"] = imagery_type
        props["extraction_method"] = meta.get("extraction_method", "ai_segmentation")
        props["model"] = meta.get("model", "unspecified")
        props["derived_from"] = "imagery_extraction"

    prov_nodes = [
        {"node_id": prov_origin_id, "node_type": "origin", "parent_ids": [],
         "label": f"Imagery source: {imagery_type}"},
        {"node_id": prov_ds_id, "node_type": "dataset", "parent_ids": [prov_origin_id],
         "label": "AI-extracted parcel boundaries"},
    ]

    return DerivedFeatureSet(
        feature_type="parcel_boundary",
        features=features,
        source_metadata=src_meta,
        provenance_nodes=prov_nodes,
        quality_weight=src_meta.quality_weight,
        evidence_note=(
            f"Parcel boundaries extracted via AI segmentation from {imagery_type}. "
            f"Positional accuracy ≈ {accuracy:.2f}m. " if accuracy else ""
            "Treated as one evidence source — NOT automatically authoritative."
        ),
    )


def geotiff_as_evidence_context(path: str) -> dict:
    """
    Load a GeoTIFF and return its spatial coverage + quality metadata.
    This lets the harmonization engine know what areas are covered
    by high-resolution imagery evidence.
    """
    try:
        meta = from_geotiff_metadata(path)
        imagery_type = "drone_ori" if "drone" in path.lower() else "unknown"
        return {
            "type": "imagery_context",
            "source": Path(path).name,
            "imagery_type": imagery_type,
            "coverage_geojson": meta["extent_wgs84"],
            "wgs84_bounds": meta["wgs84_bounds"],
            "resolution_px": {"width": meta["width_px"], "height": meta["height_px"]},
            "bands": meta["bands"],
            "quality_weight": IMAGERY_QUALITY_WEIGHTS.get(imagery_type, 0.50),
            "note": "Spatial coverage of imagery evidence — use to weight boundary observations",
        }
    except Exception as e:
        return {"type": "imagery_context", "error": str(e), "source": Path(path).name}
