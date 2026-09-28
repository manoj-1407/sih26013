"""Quick demo status check."""
import os, tempfile, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("GS_DATA_DIR", tempfile.mkdtemp())
os.environ.setdefault("GS_DEMO_MODE", "1")

from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)

# Force reload
r = c.post("/api/v1/demo/load-ward42?force_reload=true")
d = r.json()
print("Status:", d.get("status"))
print("Parcels matched:", d.get("parcels_matched"))
print("Review required:", d.get("review_required"))
print("Auto approved:", d.get("auto_approved"))
print()

for p in d.get("parcels", [])[:10]:
    print(f"  {p['parcel_id']} | decision={p['decision']:<18} | confidence={p['match_confidence']:.2f} | conflicts={p['conflict_count']} | sources={p['source_count']}")

# Check geometry on first parcel
parcels = c.get("/api/v1/cases/WARD42-DEMO/parcels").json()
p = parcels["parcels"][0]
pid = p["canonical_id"]
detail = c.get(f"/api/v1/cases/WARD42-DEMO/parcels/{pid}").json()
print(f"\nDetail for {pid}:")
print(f"  has geometry: {detail.get('geometry') is not None}")
print(f"  conflicts: {len(detail.get('conflicts', []))}")
print(f"  proposal: {detail.get('proposal', {}).get('decision')}")
if detail.get("geometry"):
    coords = detail["geometry"].get("coordinates", [[]])[0]
    if coords:
        print(f"  first coord: {coords[0]}")
