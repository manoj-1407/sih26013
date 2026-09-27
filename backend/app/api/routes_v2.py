"""GeoSamanvay API — Extended Routes (P0 gap closure).

New endpoints added in this module:
  /api/v1/formats                             Supported ingestion formats
  /api/v1/cases/{id}/datasets/upload          File-based dataset upload
  /api/v1/cases/{id}/parcels/{pid}/ulpin      Get/assign ULPIN for a parcel
  /api/v1/cases/{id}/change-detection         Run temporal change detection
  /api/v1/cases/{id}/imagery                  Register imagery-derived features
  /api/v1/names/compare                       Multilingual name comparison
  GET /api/v1/cases/{id}/ogc/conformance      OGC API Features conformance
  GET /api/v1/cases/{id}/ogc/collections      OGC API Features collections
  GET /api/v1/cases/{id}/ogc/collections/{cid}/items  Features endpoint
  GET /api/v1/cases/{id}/export/geopackage    Download GeoPackage
"""
from __future__ import annotations
import io
import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, File, Form, UploadFile, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.database import get_db, DBCanonicalParcel, DBSourceRecord
from app.models.domain import SourceType
from app.ingestion.format_adapters import from_file, from_geojson, SUPPORTED_FORMATS
from app.ingestion.imagery_adapter import adapt_building_footprints, adapt_extracted_boundaries
from app.ingestion.ingestor import ingest_dataset
from app.matching.multilingual import compare_names, NameMatchResult
from app.core.ulpin import (
    validate_ulpin, link_ulpins, extract_ulpin_from_attributes,
    generate_demo_identifier, demo_identifier_from_geometry,
)
from app.core.change_detection import detect_parcel_changes, ChangeRecord
from app.export.ogc_api import (
    make_conformance, make_collections, get_parcels_as_features,
    get_source_records_as_features, export_geopackage,
)

router_v2 = APIRouter(prefix="/api/v1")


# ─────────────────────────────────────────────────────────────────────────────
# Format discovery
# ─────────────────────────────────────────────────────────────────────────────

@router_v2.get("/formats")
def list_supported_formats():
    """List all supported ingestion file formats."""
    return {
        "supported_formats": [
            {"extension": ext, "description": desc}
            for ext, desc in SUPPORTED_FORMATS.items()
        ],
        "source_types": [t.value for t in SourceType],
        "note": "GeoJSON is always supported natively. Shapefile/GeoPackage require fiona. GeoParquet requires geopandas.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# File-based dataset upload
# ─────────────────────────────────────────────────────────────────────────────

@router_v2.post("/cases/{case_id}/datasets/upload")
async def upload_dataset(
    case_id: str,
    file: UploadFile = File(...),
    source_type: str = Form("UNKNOWN"),
    label: str = Form(""),
    authority: str = Form(""),
    source_crs: str = Form("EPSG:4326"),
    layer: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Upload a geospatial file (GeoJSON, Shapefile, GeoPackage, GeoParquet, CSV)
    and ingest it as a source dataset.
    
    Supports: .geojson, .json, .shp (in ZIP), .gpkg, .parquet, .csv, .zip
    """
    import tempfile, os
    from pathlib import Path

    content = await file.read()
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()

    # Write to temp file
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Parse file
        try:
            from app.ingestion.format_adapters import from_file as _from_file
            features = _from_file(tmp_path, layer=layer)
        except ImportError as e:
            raise HTTPException(400, f"Missing dependency for {suffix}: {e}")
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(422, f"Could not parse {filename}: {e}")

        # Validate source type
        try:
            st = SourceType(source_type)
        except ValueError:
            st = SourceType.UNKNOWN

        # Run ingestion
        result = ingest_dataset(
            case_id=case_id,
            source_type=st,
            features=features,
            source_crs=source_crs,
            label=label or filename,
            authority=authority,
            db=db,
        )

        return {
            "dataset_id": result.dataset_id,
            "filename": filename,
            "source_type": st.value,
            "accepted": len(result.accepted),
            "rejected": [{"id": r.original_id, "reason": r.reason} for r in result.rejected],
            "quality_profile": {
                "quality_score": result.quality_profile.quality_score if result.quality_profile else None,
                "quality_level": result.quality_profile.quality_level.value if result.quality_profile else None,
                "warnings": result.quality_profile.warnings if result.quality_profile else [],
            },
        }
    finally:
        os.unlink(tmp_path)


# ─────────────────────────────────────────────────────────────────────────────
# Imagery-derived feature registration
# ─────────────────────────────────────────────────────────────────────────────

class ImageryFeaturesRequest(BaseModel):
    feature_type: str = "building_footprint"   # building_footprint | parcel_boundary
    geojson: dict                               # GeoJSON FeatureCollection
    imagery_metadata: dict = Field(default_factory=dict)


@router_v2.post("/cases/{case_id}/imagery")
def register_imagery_features(
    case_id: str,
    req: ImageryFeaturesRequest,
    db: Session = Depends(get_db),
):
    """
    Register AI-extracted features from drone/satellite imagery as evidence sources.
    
    These are treated as one evidence source — NOT as authoritative boundaries.
    The provenance graph records them as imagery-derived to prevent false independence.
    """
    from app.api.routes import _audit, _get_graph
    from app.core.provenance import ProvenanceNode

    geojson_str = json.dumps(req.geojson)
    if req.feature_type == "building_footprint":
        derived = adapt_building_footprints(geojson_str, req.imagery_metadata)
        source_type = SourceType.BUILDING_FOOTPRINT
    elif req.feature_type == "parcel_boundary":
        derived = adapt_extracted_boundaries(geojson_str, req.imagery_metadata)
        source_type = SourceType.DRONE_ORI
    else:
        raise HTTPException(400, f"Unknown feature_type: {req.feature_type!r}")

    # Register provenance nodes
    graph = _get_graph(case_id)
    from app.models.database import DBProvenanceNode
    for pnode in derived.provenance_nodes:
        from app.core.provenance import ProvenanceNode as PN
        graph.add_node(PN(
            node_id=pnode["node_id"],
            node_type=pnode["node_type"],
            parent_ids=pnode.get("parent_ids", []),
            label=pnode.get("label", ""),
        ))
        db_node = DBProvenanceNode(
            node_id=pnode["node_id"],
            case_id=case_id,
            node_type=pnode["node_type"],
            parent_ids=pnode.get("parent_ids", []),
            label=pnode.get("label", ""),
        )
        db.merge(db_node)

    # Ingest features
    result = ingest_dataset(
        case_id=case_id,
        source_type=source_type,
        features=derived.features,
        label=f"Imagery-derived {req.feature_type}",
        authority=req.imagery_metadata.get("provider", "unknown"),
        db=db,
    )

    db.commit()
    _audit(db, case_id, "IMAGERY_FEATURES_REGISTERED", "system", {
        "feature_type": req.feature_type,
        "accepted": len(result.accepted),
        "quality_weight": derived.quality_weight,
    })

    return {
        "dataset_id": result.dataset_id,
        "feature_type": req.feature_type,
        "accepted": len(result.accepted),
        "quality_weight": derived.quality_weight,
        "evidence_note": derived.evidence_note,
        "provenance_nodes_added": len(derived.provenance_nodes),
    }


# ─────────────────────────────────────────────────────────────────────────────
# ULPIN
# ─────────────────────────────────────────────────────────────────────────────

@router_v2.get("/cases/{case_id}/parcels/{parcel_id}/ulpin")
def get_or_assign_ulpin(
    case_id: str,
    parcel_id: str,
    state_code: str = "15",
    district_code: str = "42",
    db: Session = Depends(get_db),
):
    """
    Get existing ULPIN for a canonical parcel (from source data), or generate
    a DEMO spatial identifier if no authoritative ULPIN is available.

    ULPIN policy:
      - If any source record for this parcel already contains a valid ULPIN
        from an authoritative source (BhuNaksha, DILRMP, state system),
        that is returned as-is.
      - Otherwise, a DEMO-ONLY spatial identifier is generated from the
        parcel centroid. This is clearly labelled as non-official.
      - We do NOT implement the official DoLR/ECCMA ULPIN algorithm.
        In production, consume ULPINs from authoritative source datasets.
    """
    parcel = db.query(DBCanonicalParcel).filter(
        DBCanonicalParcel.canonical_id == parcel_id,
        DBCanonicalParcel.case_id == case_id,
    ).first()
    if not parcel:
        raise HTTPException(404, f"Parcel {parcel_id!r} not found")

    # 1. Check if an authoritative ULPIN was supplied in source records
    if parcel.ulpin:
        r = validate_ulpin(parcel.ulpin)
        return {
            "parcel_id": parcel_id,
            "ulpin": parcel.ulpin,
            "status": "authoritative",
            "valid": r.valid,
            "state_code": r.state_code,
            "validation_message": r.message,
            "source": "authoritative_source_record",
            "note": "ULPIN supplied by source dataset — treated as authoritative.",
        }

    # 2. Check source records for a ULPIN in their attributes
    source_ids = parcel.source_record_ids or []
    if source_ids:
        source_recs = db.query(DBSourceRecord).filter(
            DBSourceRecord.record_id.in_(source_ids)
        ).all()
        for rec in source_recs:
            attrs = rec.attributes or {}
            canonical = attrs.get("_canonical", {})
            found = extract_ulpin_from_attributes({**attrs, **canonical})
            if found:
                r = validate_ulpin(found)
                parcel.ulpin = found
                db.commit()
                return {
                    "parcel_id": parcel_id,
                    "ulpin": found,
                    "status": "extracted_from_source",
                    "valid": r.valid,
                    "state_code": r.state_code,
                    "validation_message": r.message,
                    "source": rec.record_id,
                    "note": "ULPIN extracted from source record attributes.",
                }

    # 3. No authoritative ULPIN — generate DEMO identifier
    if not parcel.centroid_lon or not parcel.centroid_lat:
        if parcel.geometry_geojson:
            result = demo_identifier_from_geometry(
                parcel.geometry_geojson,
                state_code=state_code,
                district_code=district_code,
            )
        else:
            raise HTTPException(422, "Parcel has no geometry for identifier generation")
    else:
        result = generate_demo_identifier(
            parcel.centroid_lon, parcel.centroid_lat,
            state_code=state_code,
            district_code=district_code,
        )

    if not result:
        raise HTTPException(422, "Could not generate demo identifier")

    return {
        "parcel_id": parcel_id,
        "demo_identifier": result.demo_id,
        "status": "demo_only",
        "valid": True,
        "state_code": result.state_code,
        "district_code": result.district_code,
        "centroid_lat": result.centroid_lat,
        "centroid_lon": result.centroid_lon,
        "is_official_ulpin": False,
        "disclaimer": result.disclaimer,
        "note": (
            "No authoritative ULPIN found in source records. "
            "Demo identifier generated for prototype purposes only. "
            "In production, supply ULPIN from BhuNaksha/DILRMP/state land records."
        ),
    }


@router_v2.post("/ulpin/validate")
def validate_ulpin_endpoint(body: dict):
    """Validate a ULPIN string format (authoritative ULPINs from source systems)."""
    ulpin = body.get("ulpin", "")
    r = validate_ulpin(ulpin)
    return {
        "ulpin": r.ulpin,
        "valid": r.valid,
        "message": r.message,
        "state_code": r.state_code,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Change Detection
# ─────────────────────────────────────────────────────────────────────────────

@router_v2.post("/cases/{case_id}/change-detection")
def run_change_detection(case_id: str, db: Session = Depends(get_db)):
    """
    Run temporal and concurrent change detection across all matched parcels.
    Classifies: GEOMETRY_CHANGE, AREA_CHANGE, LAND_USE_CHANGE, BOUNDARY_DRIFT,
                SOURCE_DISCREPANCY, NO_CHANGE.
    """
    from app.models.database import DBCanonicalParcel, DBSourceRecord

    parcels = db.query(DBCanonicalParcel).filter(
        DBCanonicalParcel.case_id == case_id
    ).all()

    if not parcels:
        raise HTTPException(400, "No canonical parcels found. Run harmonization first.")

    parcel_results = []
    for parcel in parcels:
        rec_ids = parcel.source_record_ids or []
        if len(rec_ids) < 2:
            continue

        db_recs = db.query(DBSourceRecord).filter(
            DBSourceRecord.record_id.in_(rec_ids)
        ).all()

        change_records = []
        for r in db_recs:
            attrs = r.attributes or {}
            canonical = attrs.get("_canonical", {})
            change_records.append(ChangeRecord(
                record_id=r.record_id,
                source_type=r.source_type,
                geometry_geojson=r.geometry_geojson,
                area_sqm=r.area_sqm,
                land_use=canonical.get("land_use"),
                owner_reference=canonical.get("owner_reference"),
                capture_timestamp=r.capture_timestamp,
                attributes=canonical,
            ))

        result = detect_parcel_changes(parcel.canonical_id, change_records)
        parcel_results.append({
            "parcel_id": parcel.canonical_id,
            "records_analyzed": result.records_analyzed,
            "temporal_span_days": result.temporal_span_days,
            "earliest_observation": result.earliest_observation,
            "latest_observation": result.latest_observation,
            "change_summary": result.change_summary,
            "has_temporal_changes": result.has_temporal_changes,
            "has_concurrent_conflicts": result.has_concurrent_conflicts,
            "change_events": [
                {
                    "type": e.change_type,
                    "severity": e.severity,
                    "gap_days": e.gap_days,
                    "measure": e.measure,
                    "unit": e.measure_unit,
                    "description": e.description,
                    "is_temporal": e.is_temporal,
                }
                for e in result.change_events
            ],
        })

    temporal_count = sum(1 for r in parcel_results if r["has_temporal_changes"])
    concurrent_count = sum(1 for r in parcel_results if r["has_concurrent_conflicts"])

    return {
        "case_id": case_id,
        "parcels_analyzed": len(parcel_results),
        "parcels_with_temporal_changes": temporal_count,
        "parcels_with_concurrent_conflicts": concurrent_count,
        "results": parcel_results,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Multilingual name comparison
# ─────────────────────────────────────────────────────────────────────────────

class NameCompareRequest(BaseModel):
    name_a: str
    name_b: str


@router_v2.post("/names/compare")
def compare_owner_names(req: NameCompareRequest):
    """
    Multilingual/transliteration-aware owner name comparison.
    Handles Devanagari ↔ Roman, honorifics, patronymics, abbreviations.
    """
    result = compare_names(req.name_a, req.name_b)
    return {
        "name_a": result.name_a,
        "name_b": result.name_b,
        "normalized_a": result.normalized_a,
        "normalized_b": result.normalized_b,
        "soundex_a": result.soundex_a,
        "soundex_b": result.soundex_b,
        "soundex_match": result.soundex_match,
        "fuzzy_score_pct": result.fuzzy_score,
        "overall_similarity": round(result.overall_similarity, 4),
        "match_level": result.match_level,
        "explanation": result.explanation,
    }


# ─────────────────────────────────────────────────────────────────────────────
# OGC API Features
# ─────────────────────────────────────────────────────────────────────────────

@router_v2.get("/cases/{case_id}/ogc/conformance")
def ogc_conformance(case_id: str):
    return make_conformance()


@router_v2.get("/cases/{case_id}/ogc/collections")
def ogc_collections(case_id: str, request_url: str = ""):
    return make_collections(case_id, base_url=f"/api/v1/cases/{case_id}/ogc")


@router_v2.get("/cases/{case_id}/ogc/collections/{collection_id}/items")
def ogc_collection_items(
    case_id: str,
    collection_id: str,
    offset: int = 0,
    limit: int = 100,
    source_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """OGC API Features — paginated feature access."""
    limit = min(limit, 1000)  # cap at 1000
    if collection_id.endswith("_parcels"):
        return get_parcels_as_features(db, case_id, offset=offset, limit=limit)
    elif collection_id.endswith("_source_records"):
        return get_source_records_as_features(db, case_id, offset=offset, limit=limit, source_type=source_type)
    else:
        raise HTTPException(404, f"Collection {collection_id!r} not found")


@router_v2.get("/cases/{case_id}/ogc/collections/{collection_id}/items/{feature_id}")
def ogc_single_feature(
    case_id: str,
    collection_id: str,
    feature_id: str,
    db: Session = Depends(get_db),
):
    """OGC API Features — single feature access."""
    if collection_id.endswith("_parcels"):
        p = db.query(DBCanonicalParcel).filter(
            DBCanonicalParcel.canonical_id == feature_id,
            DBCanonicalParcel.case_id == case_id,
        ).first()
        if not p:
            raise HTTPException(404, f"Feature {feature_id!r} not found")
        return {
            "type": "Feature",
            "id": p.canonical_id,
            "geometry": p.geometry_geojson,
            "properties": {
                "canonical_id": p.canonical_id,
                "ulpin": p.ulpin,
                "area_sqm": p.area_sqm,
                "match_confidence": p.match_confidence,
                "independent_lineages": p.independent_lineages,
            },
        }
    raise HTTPException(404, f"Collection {collection_id!r} not found")


# ─────────────────────────────────────────────────────────────────────────────
# GeoPackage export
# ─────────────────────────────────────────────────────────────────────────────

@router_v2.get("/cases/{case_id}/export/geopackage")
def download_geopackage(
    case_id: str,
    include_source_records: bool = True,
    include_conflicts: bool = True,
    db: Session = Depends(get_db),
):
    """
    Export the full harmonization case as a GeoPackage (.gpkg).
    
    The GeoPackage includes:
      - canonical_parcels (harmonization proposals, NOT overwritten sources)
      - source_records (original immutable records)
      - conflicts (detected conflict table)
      - case_metadata

    Can be opened directly in QGIS, ArcGIS, GDAL, or any OGC-compliant tool.
    """
    gpkg_bytes = export_geopackage(
        db, case_id,
        include_source_records=include_source_records,
        include_conflicts=include_conflicts,
    )
    return Response(
        content=gpkg_bytes,
        media_type="application/geopackage+sqlite3",
        headers={"Content-Disposition": f"attachment; filename={case_id}_harmonization.gpkg"},
    )


@router_v2.get("/cases/{case_id}/export/geojson")
def export_geojson(
    case_id: str,
    layer: str = "parcels",
    db: Session = Depends(get_db),
):
    """Export canonical parcels or source records as GeoJSON."""
    if layer == "parcels":
        fc = get_parcels_as_features(db, case_id, limit=10000)
    elif layer == "source_records":
        fc = get_source_records_as_features(db, case_id, limit=10000)
    else:
        raise HTTPException(400, f"Unknown layer: {layer!r}. Use 'parcels' or 'source_records'")

    content = json.dumps(fc, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(
        content=content,
        media_type="application/geo+json",
        headers={"Content-Disposition": f"attachment; filename={case_id}_{layer}.geojson"},
    )
