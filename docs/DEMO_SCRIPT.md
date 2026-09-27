# GeoSamanvay — SIH Demo Script
## One ward. One conflicting parcel. One complete workflow.
### ~3 minutes. No hand-waving.

---

## Setup (before the panel enters the room)

```bash
# From repo root
docker compose up
# OR for development:
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8013
# Open http://localhost:8013 or http://localhost:8013/docs
```

Generate demo data (already committed — only run once):
```bash
python scripts/generate_demo_data.py
```

---

## Demo Narrative

**Opening line (say this):**
> "Different government agencies have surveyed the same parcel. They disagree.
> The question is not which one is right — it's: can we explain why they disagree,
> and what is the smallest safe change we can propose?"

---

## Step 1 — Create the case (30 seconds)

**UI**: Cases tab → New Case → `WARD42-DEMO-2026` / "Ward 42 Harmonization Demo"

**OR via API:**
```bash
curl -X POST http://localhost:8013/api/v1/cases \
  -H "Content-Type: application/json" \
  -d '{"case_id": "WARD42-DEMO-2026", "title": "Ward 42 Harmonization Demo"}'
```

**Say:** "We've created a harmonization case. Think of it as a workspace that
holds all the source data and the decisions made about it. Nothing is modified
until an officer explicitly approves a proposal."

---

## Step 2 — Register provenance (30 seconds)

**This is the key architectural step competitors miss.**

```bash
# Origin 1: Original 1999 Survey (source of Cadastral + Revenue)
curl -X POST http://localhost:8013/api/v1/cases/WARD42-DEMO-2026/provenance/nodes \
  -H "Content-Type: application/json" \
  -d '{"node_id": "ORIG-SURVEY-1999", "node_type": "origin", "label": "Original 1999 Revenue Survey"}'

# Origin 2: 2022 Aerial Survey (source of Municipal GIS)
curl -X POST http://localhost:8013/api/v1/cases/WARD42-DEMO-2026/provenance/nodes \
  -H "Content-Type: application/json" \
  -d '{"node_id": "ORIG-AERIAL-2022", "node_type": "origin", "label": "2022 Aerial Survey"}'

# Origin 3: 2024 Drone Campaign (source of Drone ORI layer)
curl -X POST http://localhost:8013/api/v1/cases/WARD42-DEMO-2026/provenance/nodes \
  -H "Content-Type: application/json" \
  -d '{"node_id": "ORIG-DRONE-2024", "node_type": "origin", "label": "2024 Drone ORI Campaign"}'

# Derived datasets
curl -X POST http://localhost:8013/api/v1/cases/WARD42-DEMO-2026/provenance/nodes \
  -H "Content-Type: application/json" \
  -d '{"node_id": "DS-CADASTRAL", "node_type": "dataset", "parent_ids": ["ORIG-SURVEY-1999"], "label": "Cadastral Map 2019"}'

curl -X POST http://localhost:8013/api/v1/cases/WARD42-DEMO-2026/provenance/nodes \
  -H "Content-Type: application/json" \
  -d '{"node_id": "DS-REVENUE", "node_type": "dataset", "parent_ids": ["ORIG-SURVEY-1999"], "label": "Revenue RoR Records"}'

curl -X POST http://localhost:8013/api/v1/cases/WARD42-DEMO-2026/provenance/nodes \
  -H "Content-Type: application/json" \
  -d '{"node_id": "DS-MUNICIPAL", "node_type": "dataset", "parent_ids": ["ORIG-AERIAL-2022"], "label": "Municipal GIS 2022"}'

curl -X POST http://localhost:8013/api/v1/cases/WARD42-DEMO-2026/provenance/nodes \
  -H "Content-Type: application/json" \
  -d '{"node_id": "DS-DRONE", "node_type": "dataset", "parent_ids": ["ORIG-DRONE-2024"], "label": "Drone ORI Extraction 2024"}'
```

**Switch to Provenance tab in UI. Show the graph.**

**Say:** "Here's the key insight. Four datasets, but only three independent origins.
The Cadastral and Revenue records both trace back to the 1999 survey —
they are NOT independent confirmations. Our system counts origins, not files."

---

## Step 3 — Ingest four source datasets (45 seconds)

**UI**: Ingest tab. OR via API:

```bash
# Cadastral (attach provenance node via feature properties)
curl -X POST http://localhost:8013/api/v1/cases/WARD42-DEMO-2026/datasets \
  -H "Content-Type: application/json" \
  -d @- <<'EOF'
{
  "source_type": "CADASTRAL",
  "label": "Cadastral Map 2019",
  "authority": "Survey of India",
  "features": [/* contents of data/demo/ward42/cadastral.geojson features array */]
}
EOF

# Revenue/RoR
curl -X POST http://localhost:8013/api/v1/cases/WARD42-DEMO-2026/datasets \
  -H "Content-Type: application/json" \
  -d '{"source_type": "REVENUE_ROR", "label": "Revenue RoR 2021", "features": [...]}'

# Municipal GIS
curl -X POST http://localhost:8013/api/v1/cases/WARD42-DEMO-2026/datasets \
  -H "Content-Type: application/json" \
  -d '{"source_type": "MUNICIPAL_GIS", "label": "Municipal GIS 2022", "features": [...]}'

# Drone ORI
curl -X POST http://localhost:8013/api/v1/cases/WARD42-DEMO-2026/datasets \
  -H "Content-Type: application/json" \
  -d '{"source_type": "DRONE_ORI", "label": "Drone ORI 2024", "features": [...]}'

# Buildings (for topology check)
curl -X POST http://localhost:8013/api/v1/cases/WARD42-DEMO-2026/datasets \
  -H "Content-Type: application/json" \
  -d '{"source_type": "BUILDING_FOOTPRINT", "label": "Building Footprints", "features": [...]}'
```

**Show the quality profile in response.**

**Say:** "Each dataset is profiled: geometry validity rate, duplicate IDs, missing
timestamps. The system refuses to ingest metre-range coordinates declared as degrees.
Every record gets a SHA-256 hash. The source data is now locked — nothing we do
from here modifies it."

---

## Step 4 — Run harmonization (30 seconds)

```bash
curl -X POST http://localhost:8013/api/v1/cases/WARD42-DEMO-2026/harmonize \
  -H "Content-Type: application/json" \
  -d '{
    "building_geometries": [/* building features for ripple check */]
  }'
```

**Switch to Map tab. Show the parcel map.**

**Say:** "40 records across 4 datasets matched into 10 canonical parcels.
Parcel P-1042 has 4 source records and 3 independent lineages."

---

## Step 5 — Show the conflict (60 seconds — the core of the demo)

**Click P-1042 on the map.**

**Show Info tab:**
```
Match confidence: 93%
Independent lineages: 2   ← not 4
Sources: 4
Area: ~1,240 m²
```

**Say:** "Four sources. But only two independent origins — the Cadastral and Revenue
records share a common 1999 survey lineage. They count as one observation."

**Show Evidence tab (ConfidenceExplainer):**
```
Geometry         94%    IoU=0.97, boundary offset 1.42m
Identifier      100%    Khasra 1042 exact match
Attribute        86%    Owner name 94% similar
Temporal         88%    2021 vs 2024, 3yr gap
Provenance      100%    3 independent origins confirmed

Independent lineages: 2
```

**Say:** "This is not a magic number. Each signal is explained. The 86% on
attributes reflects a minor owner-name spelling difference — transliteration
variance between the Devanagari Revenue record and the Roman-script cadastral."

**Show conflicts:**
```
🔴 BOUNDARY_OFFSET  1.42m    Cadastral vs Drone (HIGH)
🟠 AREA_MISMATCH    2.1%     Municipal vs others (MEDIUM)
🟡 OWNER_MISMATCH   94% sim  Ramesh Kumar vs Ramesh K. Kumar (MEDIUM)
```

---

## Step 6 — Minimum-change proposal (20 seconds)

**Stay on Evidence tab, show proposal section:**
```
Proposal: Drone ORI boundary used as reference (weight=0.92)
         Municipal boundary requires 0.8m adjustment
         Cadastral unchanged (already agrees with Drone within tolerance)
         Area change: 0.9%
```

**Say:** "We don't average polygons. We find the smallest defensible change:
the highest-quality source — the 2024 drone survey — becomes the reference.
The municipal geometry needs a 0.8m adjustment. The original cadastral is unchanged.
Every source record still exists, unmodified."

---

## Step 7 — The blocking moment (30 seconds — most memorable)

**Show the BLOCKED / REVIEW REQUIRED status:**
```
REVIEW REQUIRED

Reason: Building footprint BLD-W42-1042 extends 2.3m² outside
        the proposed parcel boundary (ripple check: BUILDING_OUTSIDE).
```

**Say:** "This is the feature we're most proud of. The system didn't just
check the parcel in isolation — it checked what the proposed change does
to everything touching it. The building footprint would be partially outside
the new boundary. So instead of auto-approving, the system says:
this needs a human decision."

**Show Compare tab — drag the before/after slider.**

**Say:** "Here's the boundary before harmonization — four overlapping
outlines from four sources. And here's the proposal. You can see
exactly what moved and by how much. No hidden changes."

---

## Step 8 — Officer review (20 seconds)

**Switch to Review Queue tab:**
```
P-1042   Priority: 85   REVIEW_REQUIRED
         1 conflict unresolved · 1 ripple issue
         Confidence: 93%
```

**Click "Review → Decide":**
```
Decision: APPROVED
Reason: Building footprint overlap is within accepted tolerance per
        ULB Ward 42 policy. Drone boundary confirmed by field survey.
Officer: OFFICER-W42-DY
```

**Say:** "The officer reviews the specific reason it was flagged, makes a
judgment call, and records their justification. Every step is logged."

---

## Step 9 — Evidence package (15 seconds)

**Click "Evidence ZIP" download.**

```
parcel_P-XXXXXXXX/
  source_manifest.json    ← SHA-256 hash of every source record
  normalized_features.geojson
  proposal.geojson        ← before + proposed geometry
  conflicts.json          ← all detected conflicts
  confidence.json         ← per-signal breakdown
  validation.json         ← ripple check result
  decision.json           ← APPROVED, officer ID, timestamp
  audit.jsonl             ← complete audit trail
  manifest.sha256         ← integrity check for the package itself
```

**Switch to Evidence tab. Paste the `decision.json` content:**
```
Signature verified ✓
Ed25519 — Key: KEY-GS-EXAMINER-26013-v1
```

**Say:** "This ZIP is the complete, self-contained proof of what happened.
Any government auditor can independently verify the signature
without network access, without calling our server.
If anyone modifies even one byte, verification fails."

---

## Closing line

> "Most systems help you store and view land data.
> GeoSamanvay answers a harder question: when four government datasets
> describe the same parcel differently, which ones can actually be considered
> independent evidence, what is the minimum safe change, and who approved it?"

---

## Anticipated judge questions and answers

**Q: "What if the drone data is wrong?"**
A: "The drone data is one input with a quality weight. If a GNSS ground-truth
point is available, it gets weight 1.00 and overrides the drone boundary.
Our system is designed so no single source is automatically authoritative."

**Q: "What about ULPIN?"**
A: "We validate and link ULPINs supplied by authoritative sources —
BhuNaksha, DILRMP, state land records. ULPIN identifies the parcel.
GeoSamanvay reconciles the evidence describing it."

**Q: "How is this different from ArcGIS Conflation?"**
A: "ArcGIS Conflation merges datasets. We generate a proposal and require
a human decision when there's meaningful uncertainty or topology impact.
We also explicitly track source lineage — three records from the same
origin count as one independent observation, not three votes."

**Q: "Does this replace NAKSHA?"**
A: "No. NAKSHA captures field survey data and manages the GIS workflow.
We sit beside it as a reconciliation layer — consuming its outputs
alongside revenue and municipal records to produce justified
harmonization proposals."

**Q: "Why not just use AI to pick the right boundary?"**
A: "We use AI for matching and conflict detection. But we never let AI
silently overwrite a government land record. The principle is:
AI proposes, spatial rules validate, provenance explains, human approves."

---

*GeoSamanvay — Team Aikta — SIH26013*
