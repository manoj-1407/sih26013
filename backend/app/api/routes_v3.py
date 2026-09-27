"""GeoSamanvay API — Routes v3 (demo polish + Before/After wiring).

New endpoints:
  GET /cases/{id}/parcels/{pid}/sources      source record geometries for a parcel
  GET /cases/{id}/parcels/{pid}/diff         harmonization diff data
  POST /cases/{id}/proposals/{pid}/request-survey  ground-truth request
  GET /cases/{id}/quality-report             data quality summary
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models.database import (
    get_db, DBCanonicalParcel, DBSourceRecord, DBProposal,
    DBConflict, DBDataset, DBAuditEvent
)
from app.models.domain import SourceType
from app.core.geometry import area_sqm
from shapely.geometry import shape as shapely_shape

router_v3 = APIRouter(prefix="/api/v1")


# ─────────────────────────────────────────────────────────────────────────────
# Source geometries for a parcel (feeds Before/After map)
# ─────────────────────────────────────────────────────────────────────────────

@router_v3.get("/cases/{case_id}/parcels/{parcel_id}/sources")
def get_parcel_source_geometries(
    case_id: str,
    parcel_id: str,
    db: Session = Depends(get_db),
):
    """
    Return all source record geometries for a canonical parcel as a GeoJSON
    FeatureCollection. Used by the Before/After map to show original source
    boundaries on the left side.
    """
    parcel = db.query(DBCanonicalParcel).filter(
        DBCanonicalParcel.canonical_id == parcel_id,
        DBCanonicalParcel.case_id == case_id,
    ).first()
    if not parcel:
        raise HTTPException(404, f"Parcel {parcel_id!r} not found")

    source_ids = parcel.source_record_ids or []
    records = db.query(DBSourceRecord).filter(
        DBSourceRecord.record_id.in_(source_ids)
    ).all()

    source_colors = {
        "CADASTRAL": "#3b82f6",
        "REVENUE_ROR": "#10b981",
        "MUNICIPAL_GIS": "#f59e0b",
        "DRONE_ORI": "#06b6d4",
        "BUILDING_FOOTPRINT": "#ef4444",
        "UTILITY_NETWORK": "#8b5cf6",
        "GNSS_SURVEY": "#22c55e",
        "DEFAULT": "#9aadcb",
    }

    features = []
    for r in records:
        attrs = r.attributes or {}
        canonical = attrs.get("_canonical", {})
        features.append({
            "type": "Feature",
            "geometry": r.geometry_geojson,
            "properties": {
                "record_id": r.record_id,
                "source_type": r.source_type,
                "capture_timestamp": r.capture_timestamp,
                "area_sqm": r.area_sqm,
                "owner_reference": canonical.get("owner_reference"),
                "parcel_reference": canonical.get("parcel_reference"),
                "land_use": canonical.get("land_use"),
                "color": source_colors.get(r.source_type, source_colors["DEFAULT"]),
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
        "parcel_id": parcel_id,
        "source_count": len(features),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Harmonization diff endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router_v3.get("/cases/{case_id}/parcels/{parcel_id}/diff")
def get_harmonization_diff(
    case_id: str,
    parcel_id: str,
    db: Session = Depends(get_db),
):
    """
    Compute a structured diff between source state and harmonization proposal.
    Returns: geometry changes, attribute changes, topology impact, decision.
    """
    parcel = db.query(DBCanonicalParcel).filter(
        DBCanonicalParcel.canonical_id == parcel_id,
        DBCanonicalParcel.case_id == case_id,
    ).first()
    if not parcel:
        raise HTTPException(404, f"Parcel {parcel_id!r} not found")

    proposal = db.query(DBProposal).filter(
        DBProposal.parcel_id == parcel_id
    ).order_by(DBProposal.version.desc()).first()

    conflicts = db.query(DBConflict).filter(
        DBConflict.parcel_id == parcel_id
    ).all()

    source_ids = parcel.source_record_ids or []
    source_records = db.query(DBSourceRecord).filter(
        DBSourceRecord.record_id.in_(source_ids)
    ).all()

    # Geometry diff: collect area values from all sources
    areas = []
    for r in source_records:
        if r.area_sqm:
            areas.append({"record_id": r.record_id, "source_type": r.source_type,
                          "area_sqm": r.area_sqm})

    proposed_area = None
    max_offset_m = 0.0
    if proposal and proposal.proposed_geometry_geojson:
        try:
            g = shapely_shape(proposal.proposed_geometry_geojson)
            proposed_area = area_sqm(g)
        except Exception:
            pass
        max_offset_m = proposal.match_confidence or 0.0  # confidence proxy for now

    # Attribute diff from conflicts
    attr_conflicts = [
        {
            "type": c.conflict_type,
            "severity": c.severity,
            "description": c.description,
            "measure": c.measure,
            "measure_unit": c.measure_unit,
        }
        for c in conflicts
        if c.conflict_type in (
            "OWNER_REFERENCE_MISMATCH", "LAND_USE_MISMATCH",
            "AREA_ATTRIBUTE_MISMATCH", "IDENTIFIER_MISMATCH",
        )
    ]

    # Geometry conflicts
    geo_conflicts = [
        {
            "type": c.conflict_type,
            "severity": c.severity,
            "description": c.description,
            "measure": c.measure,
            "measure_unit": c.measure_unit,
        }
        for c in conflicts
        if c.conflict_type in (
            "BOUNDARY_OFFSET", "AREA_MISMATCH", "OVERLAP", "GAP", "SHAPE_DEFORMATION"
        )
    ]

    # Change summary
    change_summary = proposal.change_summary if proposal else []
    ripple = proposal.ripple_check if proposal else {}
    decision = proposal.decision if proposal else "PENDING"
    decision_reason = proposal.decision_reason if proposal else ""

    return {
        "parcel_id": parcel_id,
        "geometry": {
            "source_areas": areas,
            "proposed_area_sqm": round(proposed_area, 2) if proposed_area else None,
            "geometry_conflicts": geo_conflicts,
            "change_summary": change_summary,
        },
        "attributes": {
            "conflicts": attr_conflicts,
        },
        "topology": {
            "ripple_check": ripple,
        },
        "decision": {
            "state": decision,
            "reason": decision_reason,
            "can_auto_approve": (decision == "AUTO_APPROVED"),
        },
        "provenance": {
            "source_count": len(source_ids),
            "independent_lineages": parcel.independent_lineages,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Ground-truth request
# ─────────────────────────────────────────────────────────────────────────────

class SurveyRequestBody(BaseModel):
    parcel_id: str
    required_observation: str
    suggested_method: str = "GNSS_RTK"
    assigned_to: Optional[str] = None
    notes: str = ""


@router_v3.post("/cases/{case_id}/proposals/{proposal_id}/request-survey")
def request_ground_truth(
    case_id: str,
    proposal_id: str,
    body: SurveyRequestBody,
    db: Session = Depends(get_db),
):
    """
    When evidence is insufficient, an officer can request a new field survey.
    The request is logged in the audit trail. When new GNSS data arrives,
    it can be ingested as a new source record and harmonization re-run.
    """
    proposal = db.query(DBProposal).filter(
        DBProposal.proposal_id == proposal_id,
        DBProposal.case_id == case_id,
    ).first()
    if not proposal:
        raise HTTPException(404, f"Proposal {proposal_id!r} not found")

    request_id = f"SURVEY-REQ-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.now(timezone.utc).isoformat()

    audit_event = DBAuditEvent(
        event_id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        timestamp_utc=timestamp,
        case_id=case_id,
        event_type="SURVEY_REQUESTED",
        actor=body.assigned_to or "officer",
        details={
            "request_id": request_id,
            "proposal_id": proposal_id,
            "parcel_id": body.parcel_id,
            "required_observation": body.required_observation,
            "suggested_method": body.suggested_method,
            "assigned_to": body.assigned_to,
            "notes": body.notes,
        },
    )
    db.add(audit_event)

    # Mark proposal as awaiting ground truth
    proposal.decision = "PENDING"
    proposal.decision_reason = f"Awaiting ground truth: {body.required_observation} ({body.suggested_method})"
    db.commit()

    return {
        "request_id": request_id,
        "case_id": case_id,
        "proposal_id": proposal_id,
        "parcel_id": body.parcel_id,
        "required_observation": body.required_observation,
        "suggested_method": body.suggested_method,
        "assigned_to": body.assigned_to,
        "timestamp": timestamp,
        "next_step": (
            f"Ingest the {body.suggested_method} observation as a new GNSS_SURVEY dataset "
            f"in case {case_id}, then re-run harmonization for parcel {body.parcel_id}."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Data quality report
# ─────────────────────────────────────────────────────────────────────────────

@router_v3.get("/cases/{case_id}/quality-report")
def get_quality_report(case_id: str, db: Session = Depends(get_db)):
    """
    Generate a data quality summary for all datasets in a case.
    Shows: records accepted, quality level, issues, SHA-256 manifest hash.
    """
    from app.core.hashing import sha256_canonical

    datasets = db.query(DBDataset).filter(DBDataset.case_id == case_id).all()
    if not datasets:
        raise HTTPException(400, "No datasets found in this case")

    dataset_reports = []
    all_content_hashes = {}

    for ds in datasets:
        profile = ds.profile or {}
        records = db.query(DBSourceRecord).filter(
            DBSourceRecord.dataset_id == ds.dataset_id
        ).count()

        dataset_reports.append({
            "dataset_id": ds.dataset_id,
            "source_type": ds.source_type,
            "label": ds.label or ds.source_type,
            "total_features": ds.total_features,
            "valid_features": ds.valid_features,
            "quality_level": ds.quality_level,
            "quality_score": profile.get("quality_score"),
            "validity_rate": profile.get("validity_rate"),
            "issues": {
                "invalid_geometries": profile.get("invalid_geometries", 0),
                "repaired_geometries": profile.get("repaired_geometries", 0),
                "duplicate_ids": profile.get("duplicate_ids", 0),
                "missing_timestamps": profile.get("missing_timestamps", 0),
                "crs_issues": profile.get("crs_issues", 0),
                "area_outliers": profile.get("area_outliers", 0),
            },
            "warnings": profile.get("warnings", []),
            "content_hash": ds.content_hash,
        })

        if ds.content_hash:
            all_content_hashes[ds.dataset_id] = ds.content_hash

    # Source manifest hash
    manifest_hash = sha256_canonical(all_content_hashes).hex_digest

    total_records = sum(d["total_features"] for d in dataset_reports)
    total_valid = sum(d["valid_features"] for d in dataset_reports)
    overall_validity = (total_valid / max(1, total_records)) * 100

    return {
        "case_id": case_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "datasets": len(datasets),
            "total_records": total_records,
            "total_valid": total_valid,
            "overall_validity_rate": round(overall_validity, 1),
        },
        "datasets": dataset_reports,
        "source_manifest_hash": manifest_hash,
        "note": (
            "Quality scores are computed from: geometry validity rate (50%), "
            "timestamp completeness (25%), duplicate-ID rate (25%). "
            "These are heuristic indicators, not ISO 19157 certified assessments."
        ),
    }
