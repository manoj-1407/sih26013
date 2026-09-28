"""GeoSamanvay API Routes — /api/v1/*

Complete REST API for the harmonization platform.
All routes use /api/v1/ prefix (fixes the old sih26013 mismatch).
"""
from __future__ import annotations
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import io

from app.models.database import (
    get_db, DBCase, DBDataset, DBSourceRecord, DBCanonicalParcel,
    DBConflict, DBProposal, DBProvenanceNode, DBAuditEvent
)
from app.models.domain import SourceType, DecisionState, ConflictSeverity
from app.ingestion.ingestor import ingest_dataset, IngestedRecord
from app.matching.matcher import ParcelMatcher
from app.conflicts.detector import detect_all_conflicts
from app.harmonization.proposer import generate_proposal
from app.topology.ripple_check import run_ripple_check
from app.review.queue import ReviewQueue, DecisionStore
from app.core.provenance import ProvenanceGraph, ProvenanceNode
from app.core.evidence_envelope import verify_envelope
from app.core.signing import get_registry, init_signing
from app.core.hashing import sha256_canonical

router = APIRouter(prefix="/api/v1")

CASE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")

# Singletons (initialized at startup)
_review_queue: ReviewQueue = ReviewQueue()
_decision_store: Optional[DecisionStore] = None
_provenance_graphs: dict[str, ProvenanceGraph] = {}


def _get_data_dir() -> Path:
    return Path(os.environ.get("GS_DATA_DIR", Path(__file__).parents[3] / "data"))


def _get_decision_store() -> DecisionStore:
    global _decision_store
    if _decision_store is None:
        _decision_store = DecisionStore(_get_data_dir())
    return _decision_store


def _get_graph(case_id: str) -> ProvenanceGraph:
    if case_id not in _provenance_graphs:
        _provenance_graphs[case_id] = ProvenanceGraph()
    return _provenance_graphs[case_id]


def _validate_case_id(case_id: str) -> str:
    if not CASE_ID_RE.match(case_id):
        raise HTTPException(400, f"Invalid case_id: {case_id!r}")
    return case_id


def _audit(db: Session, case_id: str, event_type: str, actor: str, details: dict) -> None:
    content = {"case_id": case_id, "event_type": event_type, "actor": actor, "details": details}
    event = DBAuditEvent(
        event_id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        case_id=case_id,
        event_type=event_type,
        actor=actor,
        details=details,
        event_hash=sha256_canonical(content).hex_digest,
    )
    db.add(event)
    db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────────────────────────────────────

class CreateCaseRequest(BaseModel):
    case_id: Optional[str] = None
    title: str = "Harmonization Case"
    description: str = ""


class IngestDatasetRequest(BaseModel):
    source_type: str
    label: str = ""
    authority: str = ""
    source_crs: str = "EPSG:4326"
    dataset_id: Optional[str] = None
    features: list[dict]  # GeoJSON features


class ProvenanceNodeRequest(BaseModel):
    node_id: str
    node_type: str  # origin / dataset / transformation / record
    parent_ids: list[str] = Field(default_factory=list)
    label: str = ""
    content_hash: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


class RunHarmonizationRequest(BaseModel):
    dataset_ids: Optional[list[str]] = None   # if None, use all in case
    neighbor_geometries: Optional[list[dict]] = None
    building_geometries: Optional[list[dict]] = None
    utility_geometries: Optional[list[dict]] = None
    road_row_geometries: Optional[list[dict]] = None


class ReviewDecisionRequest(BaseModel):
    decision: str   # APPROVED / REJECTED
    reason: str
    actor: str = "officer"


class VerifyEnvelopeRequest(BaseModel):
    envelope: Optional[dict] = None


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(db.bind.connect().execute.__func__(db.bind, "SELECT 1"))
    except Exception:
        pass
    from app.matching.ml_reranker import get_model_info
    ml_info = get_model_info()
    return {
        "status": "OPERATIONAL",
        "service": "GeoSamanvay — Evidence-Aware Geospatial Harmonization",
        "version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "subsystems": {
            "geometry_engine": "active",
            "crs_validator": "active",
            "provenance_graph": "active",
            "matching_engine": "active",
            "ml_reranker": "active" if ml_info["available"] else "deterministic_only",
            "conflict_detector": "active",
            "harmonization_engine": "active",
            "topology_validator": "active",
            "review_queue": "active",
            "evidence_signing": "active",
            "audit_log": "active",
        },
        "ml_reranker": ml_info,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Cases
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/cases", status_code=201)
def create_case(req: CreateCaseRequest, db: Session = Depends(get_db)):
    case_id = req.case_id or f"CASE-{uuid.uuid4().hex[:8].upper()}"
    _validate_case_id(case_id)
    existing = db.query(DBCase).filter(DBCase.case_id == case_id).first()
    if existing:
        raise HTTPException(409, f"Case {case_id!r} already exists")
    db_case = DBCase(case_id=case_id, title=req.title, description=req.description)
    db.add(db_case)
    db.commit()
    _audit(db, case_id, "CASE_CREATED", "operator", {"title": req.title})
    return {"case_id": case_id, "title": req.title, "status": "created",
            "created_at": db_case.created_at.isoformat() if db_case.created_at else None}


@router.get("/cases")
def list_cases(db: Session = Depends(get_db)):
    cases = db.query(DBCase).all()
    return {"cases": [
        {
            "case_id": c.case_id,
            "title": c.title,
            "status": c.status,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in cases
    ]}


@router.get("/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)):
    _validate_case_id(case_id)
    case = db.query(DBCase).filter(DBCase.case_id == case_id).first()
    if not case:
        raise HTTPException(404, f"Case {case_id!r} not found")
    datasets = db.query(DBDataset).filter(DBDataset.case_id == case_id).all()
    parcels = db.query(DBCanonicalParcel).filter(DBCanonicalParcel.case_id == case_id).count()
    conflicts = db.query(DBConflict).filter(DBConflict.case_id == case_id).count()
    proposals = db.query(DBProposal).filter(DBProposal.case_id == case_id).count()
    return {
        "case_id": case.case_id,
        "title": case.title,
        "description": case.description,
        "status": case.status,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "stats": {
            "datasets": len(datasets),
            "canonical_parcels": parcels,
            "conflicts": conflicts,
            "proposals": proposals,
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Datasets + Ingestion
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/cases/{case_id}/datasets")
def ingest_dataset_endpoint(case_id: str, req: IngestDatasetRequest, db: Session = Depends(get_db)):
    _validate_case_id(case_id)
    case = db.query(DBCase).filter(DBCase.case_id == case_id).first()
    if not case:
        raise HTTPException(404, f"Case {case_id!r} not found")

    try:
        source_type = SourceType(req.source_type)
    except ValueError:
        raise HTTPException(400, f"Invalid source_type: {req.source_type!r}. "
                            f"Valid: {[t.value for t in SourceType]}")

    result = ingest_dataset(
        case_id=case_id,
        source_type=source_type,
        features=req.features,
        source_crs=req.source_crs,
        label=req.label,
        authority=req.authority,
        dataset_id=req.dataset_id,
        db=db,
    )

    _audit(db, case_id, "DATASET_INGESTED", "operator", {
        "dataset_id": result.dataset_id,
        "source_type": source_type.value,
        "accepted": len(result.accepted),
        "rejected": len(result.rejected),
    })

    return {
        "dataset_id": result.dataset_id,
        "source_type": source_type.value,
        "accepted": len(result.accepted),
        "rejected": [{"id": r.original_id, "reason": r.reason} for r in result.rejected],
        "quality_profile": {
            "quality_score": result.quality_profile.quality_score if result.quality_profile else None,
            "quality_level": result.quality_profile.quality_level.value if result.quality_profile else None,
            "warnings": result.quality_profile.warnings if result.quality_profile else [],
        },
    }


@router.get("/cases/{case_id}/datasets")
def list_datasets(case_id: str, db: Session = Depends(get_db)):
    _validate_case_id(case_id)
    datasets = db.query(DBDataset).filter(DBDataset.case_id == case_id).all()
    return {"datasets": [
        {
            "dataset_id": d.dataset_id,
            "source_type": d.source_type,
            "label": d.label,
            "total_features": d.total_features,
            "valid_features": d.valid_features,
            "quality_level": d.quality_level,
        }
        for d in datasets
    ]}


# ─────────────────────────────────────────────────────────────────────────────
# Provenance
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/cases/{case_id}/provenance/nodes")
def add_provenance_node(case_id: str, req: ProvenanceNodeRequest, db: Session = Depends(get_db)):
    _validate_case_id(case_id)
    graph = _get_graph(case_id)
    node = ProvenanceNode(
        node_id=req.node_id,
        node_type=req.node_type,
        parent_ids=req.parent_ids,
        label=req.label,
        content_hash=req.content_hash,
        metadata=req.metadata,
    )
    graph.add_node(node)
    # Persist
    db_node = DBProvenanceNode(
        node_id=req.node_id,
        case_id=case_id,
        node_type=req.node_type,
        parent_ids=req.parent_ids,
        label=req.label,
        content_hash=req.content_hash,
        metadata=req.metadata,
    )
    db.merge(db_node)
    db.commit()
    return {"node_id": req.node_id, "status": "added"}


@router.get("/cases/{case_id}/provenance")
def get_provenance_graph(case_id: str, db: Session = Depends(get_db)):
    _validate_case_id(case_id)
    graph = _get_graph(case_id)
    # Also load from DB (in case of restart)
    db_nodes = db.query(DBProvenanceNode).filter(DBProvenanceNode.case_id == case_id).all()
    for n in db_nodes:
        if graph.get(n.node_id) is None:
            graph.add_node(ProvenanceNode(
                node_id=n.node_id, node_type=n.node_type,
                parent_ids=n.parent_ids or [], label=n.label or "",
                content_hash=n.content_hash,
            ))
    return graph.to_dict()


# ─────────────────────────────────────────────────────────────────────────────
# Harmonization Pipeline
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/cases/{case_id}/harmonize")
def run_harmonization(
    case_id: str,
    req: RunHarmonizationRequest,
    db: Session = Depends(get_db),
):
    """
    Run the full harmonization pipeline for a case:
    match → conflict detect → propose → ripple check → queue for review.
    """
    _validate_case_id(case_id)
    case = db.query(DBCase).filter(DBCase.case_id == case_id).first()
    if not case:
        raise HTTPException(404, f"Case {case_id!r} not found")

    # Load records from DB
    query = db.query(DBSourceRecord).filter(DBSourceRecord.case_id == case_id)
    if req.dataset_ids:
        query = query.filter(DBSourceRecord.dataset_id.in_(req.dataset_ids))
    db_records = query.all()

    # Only match parcel-type records; buildings/utilities go to ripple only
    _PARCEL_SOURCE_TYPES = {
        "CADASTRAL", "REVENUE_ROR", "MUNICIPAL_GIS", "DRONE_ORI",
        "GNSS_SURVEY", "HISTORICAL", "UNKNOWN",
    }
    db_records = [r for r in db_records if r.source_type in _PARCEL_SOURCE_TYPES]

    if len(db_records) < 2:
        raise HTTPException(400, "Need at least 2 parcel-type source records to harmonize")

    # Convert DB records to IngestedRecord objects
    ingested: list[IngestedRecord] = []
    from app.models.domain import DataQualityLevel
    for r in db_records:
        attrs = r.attributes or {}
        ingested.append(IngestedRecord(
            record_id=r.record_id,
            source_type=SourceType(r.source_type),
            dataset_id=r.dataset_id,
            case_id=r.case_id,
            geometry_wkt=r.geometry_wkt or "",
            geometry_geojson=r.geometry_geojson or {},
            source_crs=r.source_crs or "EPSG:4326",
            attributes_raw={k: v for k, v in attrs.items() if k != "_canonical"},
            attributes_canonical=attrs.get("_canonical", {}),
            capture_timestamp=r.capture_timestamp,
            provenance_node_id=r.provenance_node_id,
            content_hash=r.content_hash or "",
            bbox=(r.bbox_minx or 0, r.bbox_miny or 0, r.bbox_maxx or 0, r.bbox_maxy or 0),
            centroid=(r.centroid_lon or 0, r.centroid_lat or 0),
            area_sqm=r.area_sqm,
            quality_level=DataQualityLevel.UNKNOWN,
        ))

    # Load provenance graph
    graph = _get_graph(case_id)
    db_nodes = db.query(DBProvenanceNode).filter(DBProvenanceNode.case_id == case_id).all()
    for n in db_nodes:
        if graph.get(n.node_id) is None:
            graph.add_node(ProvenanceNode(
                node_id=n.node_id, node_type=n.node_type,
                parent_ids=n.parent_ids or [], label=n.label or "",
            ))

    # Matching
    matcher = ParcelMatcher(graph=graph if graph.all_nodes() else None)
    for rec in ingested:
        matcher.add_record(rec)

    pairs = matcher.run_matching()
    groups = matcher.group_into_parcels(pairs)

    results = []
    for group_record_ids in groups:
        group_records = [r for r in ingested if r.record_id in group_record_ids]
        if not group_records:
            continue

        parcel_id = f"P-{uuid.uuid4().hex[:8].upper()}"

        # Upsert canonical parcel
        best_match_score = 0.0
        best_evidence = {}
        for pair in pairs:
            if pair.record_id_a in group_record_ids and pair.record_id_b in group_record_ids:
                if pair.evidence.overall_score > best_match_score:
                    best_match_score = pair.evidence.overall_score
                    best_evidence = {
                        "geometry": pair.evidence.geometry_score,
                        "identifier": pair.evidence.identifier_score,
                        "attribute": pair.evidence.attribute_score,
                        "temporal": pair.evidence.temporal_score,
                        "provenance": pair.evidence.provenance_score,
                        "overall": pair.evidence.overall_score,
                        "explanation": pair.evidence.explanation,
                    }

        # Extract geometry from best-quality source record
        _best_rec_h = ingested[0]
        _best_w_h = 0.0
        for _r_h in ingested:
            if _r_h.record_id in group_record_ids:
                from app.harmonization.proposer import SOURCE_QUALITY_WEIGHTS as _SQW
                _w_h = _SQW.get(_r_h.source_type.value, 0.5)
                if _w_h > _best_w_h:
                    _best_w_h = _w_h
                    _best_rec_h = _r_h

        _attrs_h = _best_rec_h.attributes_canonical

        db_parcel = DBCanonicalParcel(
            canonical_id=parcel_id,
            case_id=case_id,
            source_record_ids=group_record_ids,
            match_method="MULTI_SIGNAL",
            match_confidence=best_match_score,
            match_evidence=best_evidence,
            independent_lineages=len(set(r.source_type for r in group_records)),
            geometry_geojson=_best_rec_h.geometry_geojson,
            centroid_lon=_best_rec_h.centroid[0] if _best_rec_h.centroid else None,
            centroid_lat=_best_rec_h.centroid[1] if _best_rec_h.centroid else None,
            area_sqm=_best_rec_h.area_sqm,
            land_use=_attrs_h.get("land_use"),
            owner_reference=_attrs_h.get("owner_reference"),
        )
        db.merge(db_parcel)
        db.flush()

        # Conflict detection
        conflicts = detect_all_conflicts(parcel_id, group_records, graph)
        for conf in conflicts:
            db_conf = DBConflict(
                conflict_id=conf.conflict_id,
                parcel_id=parcel_id,
                case_id=case_id,
                conflict_type=conf.conflict_type.value,
                severity=conf.severity.value,
                record_ids=conf.record_ids,
                measure=conf.measure,
                measure_unit=conf.measure_unit,
                description=conf.description,
                evidence=conf.evidence,
                auto_resolvable=conf.auto_resolvable,
            )
            db.merge(db_conf)

        # Harmonization proposal
        proposal = generate_proposal(
            parcel_id=parcel_id,
            records=group_records,
            conflicts=conflicts,
            graph=graph if graph.all_nodes() else None,
            match_confidence=best_match_score,
            match_evidence=best_evidence,
        )

        # Ripple check
        ripple = run_ripple_check(
            proposal_id=proposal.proposal_id,
            parcel_id=parcel_id,
            proposed_geometry=proposal.proposed_geometry or {},
            original_geometry=group_records[0].geometry_geojson if group_records else None,
            neighbors=req.neighbor_geometries,
            buildings=req.building_geometries,
            utilities=req.utility_geometries,
            road_rows=req.road_row_geometries,
        )

        # Override auto-approve if ripple check fails
        if not ripple.safe_to_auto_approve and proposal.can_auto_approve:
            proposal.can_auto_approve = False
            proposal.decision = DecisionState.REVIEW_REQUIRED
            proposal.decision_reason = f"Ripple check failed: {ripple.summary}"
            proposal.auto_reject_reasons.append(ripple.summary)

        # Persist proposal
        db_prop = DBProposal(
            proposal_id=proposal.proposal_id,
            parcel_id=parcel_id,
            case_id=case_id,
            version=proposal.version,
            proposed_geometry_geojson=proposal.proposed_geometry,
            proposed_attributes=proposal.proposed_attributes,
            change_summary=proposal.change_summary,
            conflicts_resolved=proposal.conflicts_resolved,
            conflicts_unresolved=proposal.conflicts_unresolved,
            match_confidence=proposal.match_confidence,
            confidence_components=proposal.confidence_components,
            independent_lineages=proposal.independent_lineages,
            decision=proposal.decision.value,
            decision_reason=proposal.decision_reason,
            ripple_check=ripple.to_dict(),
        )
        db.merge(db_prop)

        # Update parcel
        db_parcel.proposal_id = proposal.proposal_id
        from sqlalchemy.orm.attributes import flag_modified
        db_parcel.conflict_ids = [c.conflict_id for c in conflicts]
        flag_modified(db_parcel, "conflict_ids")

        # Enqueue for review if needed
        review_item = None
        if proposal.decision == DecisionState.REVIEW_REQUIRED:
            review_item = _review_queue.enqueue(proposal, case_id, ripple, conflicts)

        db.commit()

        results.append({
            "parcel_id": parcel_id,
            "source_count": len(group_records),
            "source_types": [r.source_type.value for r in group_records],
            "match_confidence": round(best_match_score, 4),
            "independent_lineages": proposal.independent_lineages,
            "conflicts": {
                "total": len(conflicts),
                "critical": sum(1 for c in conflicts if c.severity == ConflictSeverity.CRITICAL),
                "high": sum(1 for c in conflicts if c.severity == ConflictSeverity.HIGH),
                "medium": sum(1 for c in conflicts if c.severity == ConflictSeverity.MEDIUM),
                "low": sum(1 for c in conflicts if c.severity == ConflictSeverity.LOW),
            },
            "proposal": {
                "proposal_id": proposal.proposal_id,
                "decision": proposal.decision.value,
                "decision_reason": proposal.decision_reason,
                "can_auto_approve": proposal.can_auto_approve,
                "max_boundary_offset_m": round(proposal.max_boundary_offset_m, 2),
                "area_change_pct": round(proposal.area_change_pct * 100, 2),
                "change_summary": proposal.change_summary,
            },
            "ripple": {
                "safe_to_auto_approve": ripple.safe_to_auto_approve,
                "total_issues": ripple.total_issues,
                "summary": ripple.summary,
            },
            "review_item_id": review_item.item_id if review_item else None,
        })

    _audit(db, case_id, "HARMONIZATION_COMPLETE", "system", {
        "groups_processed": len(groups),
        "total_records": len(ingested),
    })

    return {
        "case_id": case_id,
        "total_records": len(ingested),
        "matched_groups": len(groups),
        "parcels": results,
        "review_queue_count": len(_review_queue.get_queue(case_id)),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Parcels
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/parcels")
def list_parcels(case_id: str, db: Session = Depends(get_db)):
    _validate_case_id(case_id)
    parcels = db.query(DBCanonicalParcel).filter(DBCanonicalParcel.case_id == case_id).all()

    # Count conflicts directly from the DBConflict table (reliable, no JSON mutable issue)
    from sqlalchemy import func as sqlfunc
    conflict_counts = dict(
        db.query(DBConflict.parcel_id, sqlfunc.count(DBConflict.conflict_id))
        .filter(DBConflict.case_id == case_id)
        .group_by(DBConflict.parcel_id)
        .all()
    )

    return {"parcels": [
        {
            "canonical_id": p.canonical_id,
            "ulpin": p.ulpin,
            "match_confidence": p.match_confidence,
            "independent_lineages": p.independent_lineages,
            "source_count": len(p.source_record_ids or []),
            "conflict_count": conflict_counts.get(p.canonical_id, 0),
            "proposal_id": p.proposal_id,
            "status": p.status,
            "geometry": p.geometry_geojson,
            "area_sqm": p.area_sqm,
            "land_use": p.land_use,
            "centroid_lon": p.centroid_lon,
            "centroid_lat": p.centroid_lat,
        }
        for p in parcels
    ]}


@router.get("/cases/{case_id}/parcels/{parcel_id}")
def get_parcel(case_id: str, parcel_id: str, db: Session = Depends(get_db)):
    _validate_case_id(case_id)
    parcel = db.query(DBCanonicalParcel).filter(
        DBCanonicalParcel.canonical_id == parcel_id,
        DBCanonicalParcel.case_id == case_id,
    ).first()
    if not parcel:
        raise HTTPException(404, f"Parcel {parcel_id!r} not found")

    conflicts = db.query(DBConflict).filter(DBConflict.parcel_id == parcel_id).all()
    proposal = db.query(DBProposal).filter(DBProposal.parcel_id == parcel_id).first()

    return {
        "canonical_id": parcel.canonical_id,
        "ulpin": parcel.ulpin,
        "geometry": parcel.geometry_geojson,
        "area_sqm": parcel.area_sqm,
        "land_use": parcel.land_use,
        "owner_reference": parcel.owner_reference,
        "match_confidence": parcel.match_confidence,
        "match_evidence": parcel.match_evidence,
        "independent_lineages": parcel.independent_lineages,
        "source_record_ids": parcel.source_record_ids,
        "conflicts": [
            {
                "conflict_id": c.conflict_id,
                "type": c.conflict_type,
                "severity": c.severity,
                "description": c.description,
                "measure": c.measure,
                "measure_unit": c.measure_unit,
            }
            for c in conflicts
        ],
        "proposal": {
            "proposal_id": proposal.proposal_id,
            "decision": proposal.decision,
            "decision_reason": proposal.decision_reason,
            "match_confidence": proposal.match_confidence,
            "confidence_components": proposal.confidence_components,
            "change_summary": proposal.change_summary,
            "proposed_geometry": proposal.proposed_geometry_geojson,
            "ripple_check": proposal.ripple_check,
        } if proposal else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Review Queue
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/review")
def get_review_queue(case_id: str):
    _validate_case_id(case_id)
    items = _review_queue.get_queue(case_id)
    return {
        "case_id": case_id,
        "pending_count": len(items),
        "items": [
            {
                "item_id": i.item_id,
                "proposal_id": i.proposal_id,
                "parcel_id": i.parcel_id,
                "priority": i.priority,
                "reason": i.reason,
                "conflict_types": i.conflict_types,
                "conflict_count": i.conflict_count,
                "ripple_issues": i.ripple_issues,
                "match_confidence": round(i.match_confidence, 4),
                "created_at": i.created_at,
                "status": i.status,
            }
            for i in items
        ],
    }


@router.post("/cases/{case_id}/proposals/{proposal_id}/decide")
def decide_proposal(
    case_id: str,
    proposal_id: str,
    req: ReviewDecisionRequest,
    db: Session = Depends(get_db),
):
    _validate_case_id(case_id)
    db_prop = db.query(DBProposal).filter(
        DBProposal.proposal_id == proposal_id,
        DBProposal.case_id == case_id,
    ).first()
    if not db_prop:
        raise HTTPException(404, f"Proposal {proposal_id!r} not found")

    try:
        decision = DecisionState(req.decision)
    except ValueError:
        raise HTTPException(400, f"Invalid decision: {req.decision!r}. Use APPROVED or REJECTED")

    if decision not in (DecisionState.APPROVED, DecisionState.REJECTED):
        raise HTTPException(400, "Decision must be APPROVED or REJECTED")

    db_prop.decision = decision.value
    db_prop.decision_reason = req.reason
    db_prop.decision_actor = req.actor
    db_prop.decision_timestamp = datetime.now(timezone.utc)
    db.commit()

    _audit(db, case_id, f"PROPOSAL_{decision.value}", req.actor, {
        "proposal_id": proposal_id,
        "reason": req.reason,
    })

    # Mark review queue item processed
    for item in _review_queue.get_queue(case_id):
        if item.proposal_id == proposal_id:
            _review_queue.mark_processed(item.item_id)
            break

    return {
        "proposal_id": proposal_id,
        "decision": decision.value,
        "reason": req.reason,
        "actor": req.actor,
        "timestamp": db_prop.decision_timestamp.isoformat(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Evidence & Verification
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/verify")
def verify_evidence(req: VerifyEnvelopeRequest):
    """Stateless envelope verification."""
    if not req.envelope:
        raise HTTPException(400, "envelope is required")
    valid, reason = verify_envelope(req.envelope, get_registry())
    return {"valid": valid, "reason": reason}


# ─────────────────────────────────────────────────────────────────────────────
# Export
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/parcels/{parcel_id}/export")
def export_parcel_evidence(case_id: str, parcel_id: str, db: Session = Depends(get_db)):
    """Export evidence package for a parcel as a ZIP archive."""
    _validate_case_id(case_id)
    parcel = db.query(DBCanonicalParcel).filter(
        DBCanonicalParcel.canonical_id == parcel_id,
        DBCanonicalParcel.case_id == case_id,
    ).first()
    if not parcel:
        raise HTTPException(404, f"Parcel {parcel_id!r} not found")

    db_records = db.query(DBSourceRecord).filter(
        DBSourceRecord.record_id.in_(parcel.source_record_ids or [])
    ).all()
    db_conflicts = db.query(DBConflict).filter(DBConflict.parcel_id == parcel_id).all()
    db_proposal = db.query(DBProposal).filter(DBProposal.parcel_id == parcel_id).first()

    from app.models.domain import DataQualityLevel
    from app.conflicts.detector import DetectedConflict
    from app.models.domain import ConflictType, ConflictSeverity as CS

    records = []
    for r in db_records:
        attrs = r.attributes or {}
        records.append(IngestedRecord(
            record_id=r.record_id,
            source_type=SourceType(r.source_type),
            dataset_id=r.dataset_id,
            case_id=r.case_id,
            geometry_wkt=r.geometry_wkt or "",
            geometry_geojson=r.geometry_geojson or {},
            source_crs=r.source_crs or "EPSG:4326",
            attributes_raw={},
            attributes_canonical=attrs.get("_canonical", {}),
            capture_timestamp=r.capture_timestamp,
            provenance_node_id=r.provenance_node_id,
            content_hash=r.content_hash or "",
            bbox=(r.bbox_minx or 0, r.bbox_miny or 0, r.bbox_maxx or 0, r.bbox_maxy or 0),
            centroid=(r.centroid_lon or 0, r.centroid_lat or 0),
            area_sqm=r.area_sqm,
            quality_level=DataQualityLevel.UNKNOWN,
        ))

    conflicts = [
        DetectedConflict(
            conflict_id=c.conflict_id,
            parcel_id=parcel_id,
            conflict_type=ConflictType(c.conflict_type),
            severity=CS(c.severity),
            record_ids=c.record_ids or [],
            measure=c.measure,
            measure_unit=c.measure_unit,
            description=c.description or "",
            evidence=c.evidence or {},
            auto_resolvable=c.auto_resolvable or False,
        )
        for c in db_conflicts
    ]

    from app.harmonization.proposer import ProposalResult
    proposal = ProposalResult(
        proposal_id=db_proposal.proposal_id if db_proposal else "NONE",
        parcel_id=parcel_id,
        match_confidence=db_proposal.match_confidence if db_proposal else 0.0,
        independent_lineages=db_proposal.independent_lineages if db_proposal else 0,
        proposed_geometry=db_proposal.proposed_geometry_geojson if db_proposal else None,
        proposed_attributes=db_proposal.proposed_attributes if db_proposal else {},
        change_summary=db_proposal.change_summary if db_proposal else [],
        conflicts_resolved=db_proposal.conflicts_resolved if db_proposal else [],
        conflicts_unresolved=db_proposal.conflicts_unresolved if db_proposal else [],
        decision=DecisionState(db_proposal.decision) if db_proposal else DecisionState.PENDING,
        decision_reason=db_proposal.decision_reason if db_proposal else "",
        confidence_components=db_proposal.confidence_components if db_proposal else {},
        source_weights={r.record_id: 1.0 for r in records},
    )

    from app.export.package_exporter import export_evidence_package
    zip_bytes = export_evidence_package(
        parcel_id=parcel_id,
        case_id=case_id,
        records=records,
        proposal=proposal,
        conflicts=conflicts,
        ripple=None,
        decision=None,
    )

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=parcel_{parcel_id}_evidence.zip"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# Audit
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/audit")
def get_audit_trail(case_id: str, db: Session = Depends(get_db)):
    _validate_case_id(case_id)
    events = db.query(DBAuditEvent).filter(
        DBAuditEvent.case_id == case_id
    ).order_by(DBAuditEvent.timestamp_utc).all()
    return {"events": [
        {
            "event_id": e.event_id,
            "timestamp_utc": e.timestamp_utc,
            "event_type": e.event_type,
            "actor": e.actor,
            "details": e.details,
            "event_hash": e.event_hash,
        }
        for e in events
    ]}
