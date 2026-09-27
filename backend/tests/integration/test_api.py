"""Integration tests for the GeoSamanvay API."""
import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Set data dir to a temp location before importing app
import os, tempfile
_tmpdir = tempfile.mkdtemp()
os.environ["GS_DATA_DIR"] = _tmpdir
os.environ["GS_DEMO_MODE"] = "1"

from app.main import app

client = TestClient(app)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def ward42_features(path_name: str) -> list:
    """Load Ward 42 demo GeoJSON features."""
    demo_dir = Path(__file__).parents[3] / "data" / "demo" / "ward42"
    filepath = demo_dir / path_name
    if not filepath.exists():
        pytest.skip(f"Demo data not found: {filepath}")
    with open(filepath, encoding="utf-8") as f:
        fc = json.load(f)
    return fc.get("features", [])


# ── Health ────────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "OPERATIONAL"
    assert "geometry_engine" in data["subsystems"]
    assert "evidence_signing" in data["subsystems"]


# ── Cases ─────────────────────────────────────────────────────────────────────

def test_create_case():
    r = client.post("/api/v1/cases", json={"title": "Integration Test Case"})
    assert r.status_code == 201
    data = r.json()
    assert "case_id" in data


def test_create_case_duplicate():
    r1 = client.post("/api/v1/cases", json={"case_id": "DUPLICATE-CASE", "title": "First"})
    assert r1.status_code == 201
    r2 = client.post("/api/v1/cases", json={"case_id": "DUPLICATE-CASE", "title": "Second"})
    assert r2.status_code == 409


def test_list_cases():
    r = client.get("/api/v1/cases")
    assert r.status_code == 200
    assert "cases" in r.json()


def test_invalid_case_id_rejected():
    # FastAPI normalizes path traversal attempts — either 400 or 404 is a safe rejection.
    r = client.get("/api/v1/cases/../../etc/passwd")
    assert r.status_code in (400, 404, 422)


# ── Dataset Ingestion ─────────────────────────────────────────────────────────

def test_ingest_cadastral():
    # Create case
    case_r = client.post("/api/v1/cases", json={"title": "Ingest Test"})
    case_id = case_r.json()["case_id"]

    features = ward42_features("cadastral.geojson")
    r = client.post(f"/api/v1/cases/{case_id}/datasets", json={
        "source_type": "CADASTRAL",
        "label": "Test Cadastral",
        "features": features,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["accepted"] >= 5
    assert data["quality_profile"]["quality_level"] in ("HIGH", "MEDIUM", "LOW")


def test_ingest_invalid_geometry_rejected():
    case_r = client.post("/api/v1/cases", json={"title": "Bad Geom Test"})
    case_id = case_r.json()["case_id"]
    r = client.post(f"/api/v1/cases/{case_id}/datasets", json={
        "source_type": "CADASTRAL",
        "features": [{"geometry": {"type": "Polygon", "coordinates": []}, "properties": {}}],
    })
    assert r.status_code == 200
    data = r.json()
    assert data["rejected"][0]["reason"] != ""


def test_ingest_metre_range_rejected():
    case_r = client.post("/api/v1/cases", json={"title": "Metre Test"})
    case_id = case_r.json()["case_id"]
    r = client.post(f"/api/v1/cases/{case_id}/datasets", json={
        "source_type": "CADASTRAL",
        "features": [{
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[800000, 2000000], [800100, 2000000],
                                  [800100, 2000100], [800000, 2000100], [800000, 2000000]]]
            },
            "properties": {"Khasra_No": "9999"}
        }],
    })
    data = r.json()
    # Should reject the metre-range geometry
    assert data["rejected"][0]["id"] is not None


# ── Provenance ────────────────────────────────────────────────────────────────

def test_add_provenance_nodes():
    case_r = client.post("/api/v1/cases", json={"title": "Prov Test"})
    case_id = case_r.json()["case_id"]

    nodes = [
        {"node_id": "ORIG-1999", "node_type": "origin", "label": "Survey 1999"},
        {"node_id": "DS-CAD", "node_type": "dataset", "parent_ids": ["ORIG-1999"]},
        {"node_id": "REC-1042", "node_type": "record", "parent_ids": ["DS-CAD"]},
    ]
    for n in nodes:
        r = client.post(f"/api/v1/cases/{case_id}/provenance/nodes", json=n)
        assert r.status_code == 200

    graph_r = client.get(f"/api/v1/cases/{case_id}/provenance")
    assert graph_r.status_code == 200
    graph = graph_r.json()
    assert len(graph["nodes"]) == 3
    assert len(graph["edges"]) == 2  # ORIG→DS, DS→REC


# ── Full pipeline ─────────────────────────────────────────────────────────────

def test_full_harmonization_pipeline():
    """Load cadastral + revenue, run harmonization, check output."""
    case_r = client.post("/api/v1/cases", json={"title": "Full Pipeline Test"})
    case_id = case_r.json()["case_id"]

    cad_features = ward42_features("cadastral.geojson")
    rev_features = ward42_features("revenue_ror.geojson")

    client.post(f"/api/v1/cases/{case_id}/datasets", json={
        "source_type": "CADASTRAL", "features": cad_features,
    })
    client.post(f"/api/v1/cases/{case_id}/datasets", json={
        "source_type": "REVENUE_ROR", "features": rev_features,
    })

    harm_r = client.post(f"/api/v1/cases/{case_id}/harmonize", json={})
    assert harm_r.status_code == 200
    data = harm_r.json()

    assert data["total_records"] >= 10
    assert data["matched_groups"] >= 1
    assert "parcels" in data

    for p in data["parcels"]:
        assert "match_confidence" in p
        assert "proposal" in p
        assert p["proposal"]["decision"] in ("AUTO_APPROVED", "REVIEW_REQUIRED", "BLOCKED", "PENDING")


# ── Evidence verification ─────────────────────────────────────────────────────

def test_verify_tampered_envelope_rejected():
    from app.core.evidence_envelope import build_evidence_payload, sign_evidence
    from app.core.signing import get_signing_key
    payload = build_evidence_payload(
        "T-001", "CASE-T", ["P-1"], ["R-A"], ["BOUNDARY_OFFSET"],
        {"overall": 0.9}, {}, {}, {"independent_lineages": 2},
        "REVIEW_REQUIRED", "Test",
    )
    key = get_signing_key()
    envelope = sign_evidence(payload, key)
    envelope["decision"] = "AUTO_APPROVED"  # tamper

    r = client.post("/api/v1/verify", json={"envelope": envelope})
    assert r.status_code == 200
    assert not r.json()["valid"]


def test_verify_valid_envelope():
    from app.core.evidence_envelope import build_evidence_payload, sign_evidence
    from app.core.signing import get_signing_key
    payload = build_evidence_payload(
        "T-002", "CASE-T", ["P-1"], ["R-A"], ["BOUNDARY_OFFSET"],
        {"overall": 0.9}, {}, {}, {"independent_lineages": 2},
        "REVIEW_REQUIRED", "Test",
    )
    key = get_signing_key()
    envelope = sign_evidence(payload, key)

    r = client.post("/api/v1/verify", json={"envelope": envelope})
    assert r.status_code == 200
    assert r.json()["valid"]


# ── Audit trail ───────────────────────────────────────────────────────────────

def test_audit_trail_populated():
    case_r = client.post("/api/v1/cases", json={"title": "Audit Test"})
    case_id = case_r.json()["case_id"]

    audit_r = client.get(f"/api/v1/cases/{case_id}/audit")
    assert audit_r.status_code == 200
    events = audit_r.json()["events"]
    assert any(e["event_type"] == "CASE_CREATED" for e in events)
