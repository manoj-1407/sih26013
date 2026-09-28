"""Demo loader — one-shot demo scenario setup.

POST /api/v1/demo/load-ward42
  Creates case WARD42-DEMO, ingests all 5 Ward 42 datasets,
  registers provenance graph, and runs harmonization.
  Returns the full result so the UI has everything it needs.

POST /api/v1/demo/load-nagpur
  Creates case NAGPUR-DEMO with Nagpur Sector 7 datasets.

POST /api/v1/demo/load-bengaluru
  Creates case BENGALURU-DEMO with Bengaluru Layout 3 datasets.

GET /api/v1/demo/cases
  Lists all available pre-built demo scenarios.

These endpoints are demo/dev only. They are disabled when GS_DEMO_MODE is not set.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db, DBCase
from app.models.domain import SourceType
from app.ingestion.ingestor import ingest_dataset
from app.core.provenance import ProvenanceGraph, ProvenanceNode
from app.models.database import DBProvenanceNode

router_demo = APIRouter(prefix="/api/v1/demo")

DEMO_DATA_DIR = Path(__file__).parents[3] / "data" / "demo" / "ward42"
DEMO_CASE_ID = "WARD42-DEMO"

_PARCEL_DATASETS = [
    ("cadastral.geojson",    SourceType.CADASTRAL,        "Cadastral Map 2019",   "Survey of India"),
    ("revenue_ror.geojson",  SourceType.REVENUE_ROR,      "Revenue RoR 2021",     "State Revenue Dept"),
    ("municipal_gis.geojson",SourceType.MUNICIPAL_GIS,    "Municipal GIS 2022",   "ULB Ward 42"),
    ("drone_ori.geojson",    SourceType.DRONE_ORI,        "Drone ORI 2024",       "Survey Agency"),
]
_CROSSLAYER_DATASETS = [
    ("buildings.geojson",    SourceType.BUILDING_FOOTPRINT,"Building Footprints", "Municipal Corp"),
    ("utilities.geojson",    SourceType.UTILITY_NETWORK,  "Utility Network",      "Utility Dept"),
]
_DATASETS = _PARCEL_DATASETS + _CROSSLAYER_DATASETS


def _load_geojson_features(filename: str, data_dir: Path) -> list[dict]:
    fp = data_dir / filename
    if not fp.exists():
        raise HTTPException(500, f"Demo data file not found: {filename}. Run scripts/generate_demo_data.py first.")
    with open(fp, encoding="utf-8") as f:
        fc = json.load(f)
    return fc.get("features", [])


def _load_provenance(case_id: str, db: Session, data_dir: Path) -> ProvenanceGraph:
    prov_file = data_dir / "provenance_graph.json"
    graph = ProvenanceGraph()
    if not prov_file.exists():
        return graph
    with open(prov_file, encoding="utf-8") as f:
        data = json.load(f)
    for n in data.get("nodes", []):
        node = ProvenanceNode(
            node_id=n["node_id"],
            node_type=n["node_type"],
            parent_ids=n.get("parent_ids", []),
            label=n.get("label", ""),
        )
        graph.add_node(node)
        db_node = DBProvenanceNode(
            node_id=n["node_id"],
            case_id=case_id,
            node_type=n["node_type"],
            parent_ids=n.get("parent_ids", []),
            label=n.get("label", ""),
        )
        db.merge(db_node)
    db.commit()
    return graph


def _load_demo_case(
    case_id: str,
    title: str,
    data_dir_name: str,
    force_reload: bool,
    db: Session,
    buildings_file: Optional[str] = None,
    utilities_file: Optional[str] = None,
) -> dict:
    """Generic demo case loader.

    Idempotent: if the case already exists, returns its current state
    unless force_reload=true.

    Loads the four standard parcel datasets (cadastral, revenue_ror,
    municipal_gis, drone_ori) plus optional buildings and utilities
    cross-layer files from ``data/demo/<data_dir_name>/``.
    """
    if os.environ.get("GS_DEMO_MODE", "1") != "1":
        raise HTTPException(403, "Demo loader only available in GS_DEMO_MODE=1")

    data_dir = Path(__file__).parents[3] / "data" / "demo" / data_dir_name

    # Check if already exists
    existing = db.query(DBCase).filter(DBCase.case_id == case_id).first()
    if existing and not force_reload:
        return {
            "status": "already_loaded",
            "case_id": case_id,
            "message": f"{title} demo already loaded. Use force_reload=true to reload.",
        }

    # Force reload: wipe all previous data for this case
    if existing and force_reload:
        from app.models.database import (
            DBDataset, DBSourceRecord, DBCanonicalParcel,
            DBConflict, DBProposal, DBProvenanceNode, DBAuditEvent
        )
        # Clear in dependency order
        db.query(DBProposal).filter(DBProposal.case_id == case_id).delete(synchronize_session=False)
        db.query(DBConflict).filter(DBConflict.case_id == case_id).delete(synchronize_session=False)
        db.query(DBCanonicalParcel).filter(DBCanonicalParcel.case_id == case_id).delete(synchronize_session=False)
        db.query(DBSourceRecord).filter(DBSourceRecord.case_id == case_id).delete(synchronize_session=False)
        db.query(DBDataset).filter(DBDataset.case_id == case_id).delete(synchronize_session=False)
        db.query(DBProvenanceNode).filter(DBProvenanceNode.case_id == case_id).delete(synchronize_session=False)
        db.query(DBAuditEvent).filter(DBAuditEvent.case_id == case_id).delete(synchronize_session=False)
        db.commit()
        # Reset in-memory caches
        from app.api.routes import _review_queue, _provenance_graphs
        if hasattr(_review_queue, '_items'):
            _review_queue._items = {k: v for k, v in _review_queue._items.items() if v.case_id != case_id}
        _provenance_graphs.pop(case_id, None)

    # Create case
    from app.api.routes import _audit
    if not existing or force_reload:
        db.merge(DBCase(
            case_id=case_id,
            title=title,
            description=f"Synthetic demo case: {title}",
        ))
        db.commit()
        _audit(db, case_id, "CASE_CREATED", "demo_loader", {"title": title})

    # Ingest provenance graph and merge into in-memory graph
    from app.api.routes import _get_graph
    graph = _load_provenance(case_id, db, data_dir)
    main_graph = _get_graph(case_id)
    for node in graph.all_nodes():
        if main_graph.get(node.node_id) is None:
            main_graph.add_node(node)

    # Build the dataset list for this case (always 4 parcel sources, optional cross-layer)
    parcel_datasets = [
        ("cadastral.geojson",    SourceType.CADASTRAL,         "Cadastral Map 2019",   "Survey of India"),
        ("revenue_ror.geojson",  SourceType.REVENUE_ROR,       "Revenue RoR 2021",     "State Revenue Dept"),
        ("municipal_gis.geojson",SourceType.MUNICIPAL_GIS,     "Municipal GIS 2022",   "ULB"),
        ("drone_ori.geojson",    SourceType.DRONE_ORI,         "Drone ORI 2024",       "Survey Agency"),
    ]
    crosslayer_datasets = []
    if buildings_file:
        crosslayer_datasets.append(
            (buildings_file, SourceType.BUILDING_FOOTPRINT, "Building Footprints", "Municipal Corp")
        )
    if utilities_file:
        crosslayer_datasets.append(
            (utilities_file, SourceType.UTILITY_NETWORK, "Utility Network", "Utility Dept")
        )
    all_datasets = parcel_datasets + crosslayer_datasets

    # Ingest all datasets
    ingest_results = []
    for filename, source_type, label, authority in all_datasets:
        features = _load_geojson_features(filename, data_dir)
        result = ingest_dataset(
            case_id=case_id,
            source_type=source_type,
            features=features,
            label=label,
            authority=authority,
            db=db,
        )
        ingest_results.append({
            "dataset_id": result.dataset_id,
            "source_type": source_type.value,
            "label": label,
            "accepted": len(result.accepted),
            "rejected": len(result.rejected),
            "quality_level": result.quality_profile.quality_level.value if result.quality_profile else "UNKNOWN",
        })

    # Load cross-layer features for ripple check
    building_features = []
    utility_features = []
    if buildings_file:
        building_features = _load_geojson_features(buildings_file, data_dir)
    if utilities_file:
        utility_features = _load_geojson_features(utilities_file, data_dir)

    from app.models.database import DBSourceRecord, DBDataset
    from app.models.domain import DataQualityLevel
    from app.matching.matcher import ParcelMatcher
    from app.conflicts.detector import detect_all_conflicts
    from app.harmonization.proposer import generate_proposal
    from app.topology.ripple_check import run_ripple_check
    from app.review.queue import ReviewQueue
    from app.ingestion.ingestor import IngestedRecord
    import uuid

    from app.api.routes import _review_queue

    # Separate parcel records from cross-layer records
    PARCEL_SOURCE_TYPES = {
        SourceType.CADASTRAL.value, SourceType.REVENUE_ROR.value,
        SourceType.MUNICIPAL_GIS.value, SourceType.DRONE_ORI.value,
        SourceType.GNSS_SURVEY.value, SourceType.HISTORICAL.value,
    }

    db_records = db.query(DBSourceRecord).filter(
        DBSourceRecord.case_id == case_id
    ).all()

    ingested: list[IngestedRecord] = []
    for r in db_records:
        if r.source_type not in PARCEL_SOURCE_TYPES:
            continue  # skip buildings/utilities from matching
        attrs = r.attributes or {}
        ingested.append(IngestedRecord(
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

    matcher = ParcelMatcher(graph=main_graph if main_graph.all_nodes() else None)
    for rec in ingested:
        matcher.add_record(rec)

    pairs = matcher.run_matching()
    groups = matcher.group_into_parcels(pairs)

    from app.models.database import DBCanonicalParcel, DBConflict, DBProposal
    from app.models.domain import ConflictSeverity, DecisionState

    parcel_results = []
    for group_ids in groups:
        group_recs = [r for r in ingested if r.record_id in group_ids]
        if not group_recs:
            continue

        parcel_id = f"P-{uuid.uuid4().hex[:8].upper()}"

        best_conf = 0.0
        best_ev = {}
        for pair in pairs:
            if pair.record_id_a in group_ids and pair.record_id_b in group_ids:
                if pair.evidence.overall_score > best_conf:
                    best_conf = pair.evidence.overall_score
                    best_ev = {
                        "geometry": pair.evidence.geometry_score,
                        "identifier": pair.evidence.identifier_score,
                        "attribute": pair.evidence.attribute_score,
                        "temporal": pair.evidence.temporal_score,
                        "provenance": pair.evidence.provenance_score,
                        "overall": pair.evidence.overall_score,
                        "explanation": pair.evidence.explanation,
                    }

        # Use best-weight source geometry for the canonical parcel
        _best_rec = group_recs[0]
        _best_weight = 0.0
        for _rec in group_recs:
            from app.harmonization.proposer import SOURCE_QUALITY_WEIGHTS
            _w = SOURCE_QUALITY_WEIGHTS.get(_rec.source_type.value, 0.5)
            if _w > _best_weight:
                _best_weight = _w
                _best_rec = _rec

        # Extract geometry metadata
        _geom_json = _best_rec.geometry_geojson
        _bbox = _best_rec.bbox
        _centroid = _best_rec.centroid
        _area = _best_rec.area_sqm

        # Get canonical attributes from best record
        _attrs = _best_rec.attributes_canonical
        _land_use = _attrs.get("land_use")
        _owner = _attrs.get("owner_reference")

        db_parcel = DBCanonicalParcel(
            canonical_id=parcel_id,
            case_id=case_id,
            source_record_ids=group_ids,
            match_method="MULTI_SIGNAL",
            match_confidence=best_conf,
            match_evidence=best_ev,
            independent_lineages=len(set(r.source_type for r in group_recs)),
            geometry_geojson=_geom_json,
            centroid_lon=_centroid[0] if _centroid else None,
            centroid_lat=_centroid[1] if _centroid else None,
            area_sqm=_area,
            land_use=_land_use,
            owner_reference=_owner,
        )
        db.merge(db_parcel)
        db.flush()

        conflicts = detect_all_conflicts(parcel_id, group_recs, main_graph)
        for conf in conflicts:
            db.merge(DBConflict(
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
            ))

        proposal = generate_proposal(
            parcel_id=parcel_id,
            records=group_recs,
            conflicts=conflicts,
            graph=main_graph if main_graph.all_nodes() else None,
            match_confidence=best_conf,
            match_evidence=best_ev,
        )

        # Build neighbor parcel geometries for ripple check
        neighbor_geoms = [
            {"parcel_id": r.canonical_id, "geometry": r.geometry_geojson}
            for r in db.query(DBCanonicalParcel).filter(
                DBCanonicalParcel.case_id == case_id,
                DBCanonicalParcel.canonical_id != parcel_id,
            ).all()
            if r.geometry_geojson
        ]

        ripple = run_ripple_check(
            proposal_id=proposal.proposal_id,
            parcel_id=parcel_id,
            proposed_geometry=proposal.proposed_geometry or {},
            original_geometry=group_recs[0].geometry_geojson if group_recs else None,
            neighbors=neighbor_geoms or None,
            buildings=[
                {"building_id": f.get("properties", {}).get("building_id", "BLD"),
                 "geometry": f.get("geometry")}
                for f in building_features if f.get("geometry")
            ] or None,
            utilities=[
                {"utility_id": f.get("properties", {}).get("utility_id", "UTIL"),
                 "type": f.get("properties", {}).get("type", "utility"),
                 "geometry": f.get("geometry")}
                for f in utility_features if f.get("geometry")
            ] or None,
        )

        if not ripple.safe_to_auto_approve and proposal.can_auto_approve:
            proposal.can_auto_approve = False
            proposal.decision = DecisionState.REVIEW_REQUIRED
            proposal.decision_reason = f"Ripple check: {ripple.summary}"
            proposal.auto_reject_reasons.append(ripple.summary)

        db.merge(DBProposal(
            proposal_id=proposal.proposal_id,
            parcel_id=parcel_id,
            case_id=case_id,
            version=1,
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
        ))
        db_parcel.proposal_id = proposal.proposal_id
        # Force SQLAlchemy to detect the JSON list mutations
        from sqlalchemy.orm.attributes import flag_modified
        db_parcel.conflict_ids = [c.conflict_id for c in conflicts]
        flag_modified(db_parcel, "conflict_ids")

        if proposal.decision == DecisionState.REVIEW_REQUIRED:
            _review_queue.enqueue(proposal, case_id, ripple, conflicts)

        parcel_results.append({
            "parcel_id": parcel_id,
            "source_count": len(group_recs),
            "match_confidence": round(best_conf, 4),
            "independent_lineages": proposal.independent_lineages,
            "conflict_count": len(conflicts),
            "decision": proposal.decision.value,
            "ripple_safe": ripple.safe_to_auto_approve,
            "ripple_issues": ripple.total_issues,
        })

    db.commit()

    from app.api.routes import _audit
    _audit(db, case_id, "DEMO_LOADED", "demo_loader", {
        "parcels": len(parcel_results),
        "review_needed": sum(1 for p in parcel_results if p["decision"] == "REVIEW_REQUIRED"),
    })

    review_count = sum(1 for p in parcel_results if p["decision"] == "REVIEW_REQUIRED")
    auto_count = sum(1 for p in parcel_results if p["decision"] == "AUTO_APPROVED")

    return {
        "status": "loaded",
        "case_id": case_id,
        "datasets_ingested": ingest_results,
        "parcels_matched": len(parcel_results),
        "auto_approved": auto_count,
        "review_required": review_count,
        "parcels": parcel_results,
        "next": f"Open http://localhost:8013 → select case {case_id} → Map tab",
    }


# ---------------------------------------------------------------------------
# Route endpoints
# ---------------------------------------------------------------------------

@router_demo.post("/load-ward42")
def load_ward42_demo(
    force_reload: bool = False,
    db: Session = Depends(get_db),
):
    """One-shot Ward 42 demo setup (Pune, Maharashtra)."""
    return _load_demo_case(
        case_id="WARD42-DEMO",
        title="Ward 42 — Harmonization Demo (Pune)",
        data_dir_name="ward42",
        force_reload=force_reload,
        db=db,
        buildings_file="buildings.geojson",
        utilities_file="utilities.geojson",
    )


@router_demo.post("/load-nagpur")
def load_nagpur_demo(
    force_reload: bool = False,
    db: Session = Depends(get_db),
):
    """One-shot Nagpur Sector 7 demo setup."""
    return _load_demo_case(
        case_id="NAGPUR-DEMO",
        title="Nagpur Sector 7 — Boundary Conflict Demo",
        data_dir_name="nagpur_sector7",
        force_reload=force_reload,
        db=db,
    )


@router_demo.post("/load-bengaluru")
def load_bengaluru_demo(
    force_reload: bool = False,
    db: Session = Depends(get_db),
):
    """One-shot Bengaluru Layout 3 demo setup."""
    return _load_demo_case(
        case_id="BENGALURU-DEMO",
        title="Bengaluru Layout 3 — Encroachment Demo",
        data_dir_name="bengaluru_layout3",
        force_reload=force_reload,
        db=db,
    )


@router_demo.get("/cases")
def list_demo_cases():
    """List all available pre-built demo scenarios."""
    return {
        "demo_cases": [
            {
                "case_id": "WARD42-DEMO",
                "title": "Ward 42, Pune",
                "description": "10 parcels across 4 source datasets. Parcel 1042 has a 1.42m boundary offset between cadastral and drone sources.",
                "city": "Pune, Maharashtra",
                "coordinates": [73.8567, 18.5204],
                "parcels": 10, "sources": 4,
                "key_conflict": "BOUNDARY_OFFSET — 1.42m offset on Parcel 1042",
                "endpoint": "/api/v1/demo/load-ward42",
            },
            {
                "case_id": "NAGPUR-DEMO",
                "title": "Sector 7, Nagpur",
                "description": "6 parcels. Parcel N-203 has a 1.1m commercial-zone boundary discrepancy.",
                "city": "Nagpur, Maharashtra",
                "coordinates": [79.0882, 21.1458],
                "parcels": 6, "sources": 4,
                "key_conflict": "BOUNDARY_OFFSET — 1.1m on Parcel N-203",
                "endpoint": "/api/v1/demo/load-nagpur",
            },
            {
                "case_id": "BENGALURU-DEMO",
                "title": "Layout 3, Bengaluru",
                "description": "5 parcels. Parcel B-303 encroaches 2.1m beyond the municipal boundary.",
                "city": "Bengaluru, Karnataka",
                "coordinates": [77.5946, 12.9716],
                "parcels": 5, "sources": 4,
                "key_conflict": "BOUNDARY_OFFSET — 2.1m encroachment on B-303",
                "endpoint": "/api/v1/demo/load-bengaluru",
            },
        ]
    }
