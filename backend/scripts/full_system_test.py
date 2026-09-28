"""Full system test — simulates clicking through every panel in the UI."""
import os, tempfile, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["GS_DATA_DIR"] = tempfile.mkdtemp()
os.environ["GS_DEMO_MODE"] = "1"

from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)
PASS = "✓"; FAIL = "✗"; WARN = "⚠"
errors = []

def check(label, condition, detail=""):
    if condition:
        print(f"  {PASS} {label}")
    else:
        print(f"  {FAIL} {label}" + (f" — {detail}" if detail else ""))
        errors.append(label)

print("\n═══════════════════════════════════════")
print("  GeoSamanvay Full System Test")
print("═══════════════════════════════════════\n")

# 1. Health
print("[1] Health check")
r = c.get("/api/v1/health")
check("Status 200", r.status_code == 200)
d = r.json()
check("System OPERATIONAL", d.get("status") == "OPERATIONAL")
check("All subsystems active", all(v in ("active","deterministic_only") for v in d.get("subsystems",{}).values()))

# 2. Demo load
print("\n[2] Load Ward 42 demo")
r = c.post("/api/v1/demo/load-ward42?force_reload=true")
check("Demo loads successfully", r.status_code == 200, r.text[:200])
d = r.json()
check("Parcels matched", d.get("parcels_matched", 0) >= 5, str(d.get("parcels_matched")))
check("Has review items", d.get("review_required", 0) > 0, str(d.get("review_required")))
check("Datasets ingested", len(d.get("datasets_ingested", [])) >= 4)

# 3. Cases list
print("\n[3] Cases list")
r = c.get("/api/v1/cases")
check("Cases endpoint 200", r.status_code == 200)
cases = r.json().get("cases", [])
check("WARD42-DEMO exists", any(c_["case_id"] == "WARD42-DEMO" for c_ in cases))

# 4. Case detail
print("\n[4] Case detail with stats")
r = c.get("/api/v1/cases/WARD42-DEMO")
check("Case detail 200", r.status_code == 200)
d = r.json()
check("Has stats", d.get("stats") is not None)
check("Has parcels in stats", d.get("stats", {}).get("canonical_parcels", 0) >= 5)

# 5. Parcel list with geometry
print("\n[5] Parcels list (must include geometry for map)")
r = c.get("/api/v1/cases/WARD42-DEMO/parcels")
check("Parcels endpoint 200", r.status_code == 200)
parcels = r.json().get("parcels", [])
check("Has parcels", len(parcels) >= 5, f"got {len(parcels)}")
with_geom = [p for p in parcels if p.get("geometry") is not None]
check("Parcels have geometry for map", len(with_geom) >= 5, f"{len(with_geom)}/{len(parcels)} have geometry")
with_conf = [p for p in parcels if p.get("match_confidence", 0) > 0.5]
check("Parcels have confidence scores", len(with_conf) >= 5)
print(f"     Sample: {parcels[0]['canonical_id']} | conf={parcels[0].get('match_confidence',0):.2f} | conflicts={parcels[0].get('conflict_count',0)} | has_geom={parcels[0].get('geometry') is not None}")

# 6. Parcel detail
print("\n[6] Parcel detail")
pid = parcels[0]["canonical_id"]
r = c.get(f"/api/v1/cases/WARD42-DEMO/parcels/{pid}")
check("Parcel detail 200", r.status_code == 200)
d = r.json()
check("Has geometry in detail", d.get("geometry") is not None)
check("Has conflicts list", isinstance(d.get("conflicts"), list))
check("Has proposal", d.get("proposal") is not None)
check("Proposal has decision", d.get("proposal", {}).get("decision") in ("AUTO_APPROVED","REVIEW_REQUIRED","BLOCKED","PENDING"))
check("Has confidence components", isinstance(d.get("proposal", {}).get("confidence_components"), dict))
if d.get("conflicts"):
    print(f"     Conflicts: {len(d['conflicts'])} — first: {d['conflicts'][0]['type']} ({d['conflicts'][0]['severity']})")

# 7. Source geometries (for before/after map)
print("\n[7] Source geometries endpoint")
r = c.get(f"/api/v1/cases/WARD42-DEMO/parcels/{pid}/sources")
check("Sources endpoint 200", r.status_code == 200)
d = r.json()
check("Is FeatureCollection", d.get("type") == "FeatureCollection")
check("Has source features", len(d.get("features", [])) >= 2)
if d.get("features"):
    f0 = d["features"][0]
    check("Source has geometry", f0.get("geometry") is not None)
    check("Source has source_type", f0.get("properties", {}).get("source_type") is not None)
    print(f"     Sources: {[f['properties'].get('source_type','?') for f in d['features']]}")

# 8. Review queue
print("\n[8] Review queue")
r = c.get("/api/v1/cases/WARD42-DEMO/review")
check("Review queue 200", r.status_code == 200)
d = r.json()
check("Has pending items", d.get("pending_count", 0) > 0, f"pending={d.get('pending_count')}")
items = d.get("items", [])
check("Items have priority", all(isinstance(i.get("priority"), (int, float)) for i in items[:3]))

# 9. Officer decision
print("\n[9] Officer decision (approve)")
if items:
    proposal_id = items[0]["proposal_id"]
    parcel_id_r = items[0]["parcel_id"]
    r = c.post(f"/api/v1/cases/WARD42-DEMO/proposals/{proposal_id}/decide",
               json={"decision": "APPROVED", "reason": "System test approval — boundary within policy", "actor": "TEST_OFFICER"})
    check("Decision recorded 200", r.status_code == 200, r.text[:100])
    check("Decision is APPROVED", r.json().get("decision") == "APPROVED")

# 10. Harmonization diff
print("\n[10] Harmonization diff")
r = c.get(f"/api/v1/cases/WARD42-DEMO/parcels/{pid}/diff")
check("Diff endpoint 200", r.status_code == 200)
d = r.json()
check("Has geometry diff", "geometry" in d)
check("Has decision", "decision" in d)
check("Has provenance", "provenance" in d)

# 11. Evidence verification
print("\n[11] Evidence verification")
from app.core.evidence_envelope import build_evidence_payload, sign_evidence
from app.core.signing import get_signing_key
payload = build_evidence_payload("SYS-TEST","WARD42-DEMO",["P-TEST"],["R-A"],["BOUNDARY_OFFSET"],{"overall":0.9},{},{},{"independent_lineages":2},"REVIEW_REQUIRED","System test")
envelope = sign_evidence(payload, get_signing_key())
r = c.post("/api/v1/verify", json={"envelope": envelope})
check("Valid envelope verifies", r.status_code == 200 and r.json().get("valid") is True)
# Tamper test
envelope["decision"] = "AUTO_APPROVED"
r = c.post("/api/v1/verify", json={"envelope": envelope})
check("Tampered envelope rejected", r.json().get("valid") is False)

# 12. GeoPackage export
print("\n[12] GeoPackage export")
r = c.get("/api/v1/cases/WARD42-DEMO/export/geopackage")
check("GeoPackage 200", r.status_code == 200)
check("Correct MIME type", "geopackage" in r.headers.get("content-type",""))
check("Non-empty file", len(r.content) > 500)

# 13. Quality report
print("\n[13] Quality report")
r = c.get("/api/v1/cases/WARD42-DEMO/quality-report")
check("Quality report 200", r.status_code == 200)
d = r.json()
check("Has summary", d.get("summary") is not None)
check("Has datasets", len(d.get("datasets", [])) >= 4)
check("Has manifest hash", d.get("source_manifest_hash") is not None)

# 14. OGC API
print("\n[14] OGC API Features")
r = c.get("/api/v1/cases/WARD42-DEMO/ogc/collections")
check("OGC collections 200", r.status_code == 200)
r = c.get("/api/v1/cases/WARD42-DEMO/ogc/collections/WARD42-DEMO_parcels/items")
check("OGC items 200", r.status_code == 200)
d = r.json()
check("OGC returns FeatureCollection", d.get("type") == "FeatureCollection")

# 15. Audit trail
print("\n[15] Audit trail")
r = c.get("/api/v1/cases/WARD42-DEMO/audit")
check("Audit 200", r.status_code == 200)
events = r.json().get("events", [])
check("Has events", len(events) > 0)
etypes = {e["event_type"] for e in events}
check("CASE_CREATED logged", "CASE_CREATED" in etypes or "DEMO_LOADED" in etypes)

# 16. Security checks
print("\n[16] Security checks")
r = c.get("/api/v1/cases/CASE@INVALID!")
check("Invalid case_id rejected", r.status_code in (400, 404, 422))
r = c.post("/api/v1/cases/WARD42-DEMO/datasets", json={"source_type":"CADASTRAL","features":[{"geometry":{"type":"Polygon","coordinates":[]},"properties":{}}]})
check("Invalid geometry rejected", r.status_code == 200 and r.json().get("accepted",1) == 0)
r = c.post("/api/v1/verify", json={})
check("Empty verify body rejected", r.status_code in (400, 422))

# 17. Name comparison
print("\n[17] Multilingual name comparison")
r = c.post("/api/v1/names/compare", json={"name_a": "Shri Ramesh Kumar", "name_b": "Ramesh K. Kumar"})
check("Name compare 200", r.status_code == 200)
d = r.json()
check("Returns similarity score", d.get("fuzzy_score_pct", 0) > 0)
check("Returns match level", d.get("match_level") in ("EXACT","HIGH","MEDIUM","LOW","NO_MATCH"))

# 18. ULPIN
print("\n[18] ULPIN validation")
r = c.post("/api/v1/ulpin/validate", json={"ulpin": "15421852073856"})
check("Valid ULPIN accepted", r.status_code == 200 and r.json().get("valid") is True)
r = c.post("/api/v1/ulpin/validate", json={"ulpin": "INVALID"})
check("Invalid ULPIN rejected", r.json().get("valid") is False)

# 19. Formats listing
print("\n[19] Format support")
r = c.get("/api/v1/formats")
check("Formats endpoint 200", r.status_code == 200)
check("Lists GeoJSON", any("geojson" in f.get("extension","") for f in r.json().get("supported_formats",[])))

# 20. Change detection
print("\n[20] Change detection")
r = c.post("/api/v1/cases/WARD42-DEMO/change-detection")
check("Change detection runs", r.status_code in (200, 400))

# ── Summary ──────────────────────────────────────────────────────────────────
print(f"\n═══════════════════════════════════════")
print(f"  RESULT: {len(errors)} failures")
if errors:
    print(f"  Failed checks:")
    for e in errors:
        print(f"    {FAIL} {e}")
else:
    print(f"  ALL CHECKS PASSED")
print(f"═══════════════════════════════════════\n")
