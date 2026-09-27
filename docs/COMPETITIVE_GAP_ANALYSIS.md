# GeoSamanvay — Competitive Gap Analysis & Technical Differentiation
## SIH26013 · Team Aikta

---

## 1. Competition Landscape (verified from public sources, Sept 2026)

| Team / Project | Approach | Public Evidence |
|---|---|---|
| **A.L.I.G.N.** (Autonomous Land Integration & GeoAI Network) | Legacy cadastral map warping → AI boundary detection (FastSAM/SAM-2) → TPS warping → 3D extrusion → ULPIN → encroachment → multilingual matching | Public GitHub repo, live Vercel app, preloaded urban sectors (Pune, Nagpur, Thane) |
| **THINK TWICE / GIS AutoPilot** | YOLOv11-seg + GeoPandas/Shapely + MapLibre + QGIS — illegal structure/encroachment detection via GeoAI | LinkedIn posts with implementation details |
| **Flugelsoft** | Multi-source harmonization + conflict queue + AI boundary snap + ownership string matching + live app | Public demo with conflict examples, confidence scores, auto-actions |
| **HACKAHOLICS** | Confirmed working on PS26013 | LinkedIn team post |
| **HORCRUX** | Confirmed cleared internal SIH for PS26013 | LinkedIn team post |

**Field size**: ~20 submissions (SIH portal) vs 500 slots — unusually small field.

---

## 2. What Competitors Have vs. What We Have

### A.L.I.G.N. Gap Analysis

| A.L.I.G.N. Feature | GeoSamanvay Equivalent | Our Advantage |
|---|---|---|
| AI boundary detection (FastSAM/SAM-2) | Imagery adapter — consumes AI-extracted boundaries as evidence | We treat AI output as *evidence*, not as the authoritative answer |
| TPS warping / elastic map alignment | Minimum-change reconciliation | We reconcile, not warp — original records preserved |
| 3D building extrusion | Building footprint cross-layer topology check | We check building-parcel spatial relationships for topology violations |
| ULPIN generation | ✅ ULPIN module (14-digit, coordinate-embedded, DoLR spec) | Same |
| Multilingual owner matching (IndicSoundex) | ✅ Multilingual module: Devanagari↔Roman, IndicSoundex variant, RapidFuzz | Same capability, different implementation |
| Before/after map comparison | ✅ Before/After slider map component | Direct visual response |
| Encroachment detection | Building/utility/ROW cross-layer checks in ripple engine | We detect AND explain AND gate auto-approval |
| "Dispute-free digital maps" claim | **We explicitly do NOT make this claim** | Honest governance: proposal, not overwrite |

**Key differentiation**: A.L.I.G.N.'s philosophy is "fix the old map". Ours is "reconcile conflicting observations without destroying the originals".

### THINK TWICE Gap Analysis

| THINK TWICE Feature | GeoSamanvay Equivalent | Our Advantage |
|---|---|---|
| YOLOv11-seg | Imagery adapter ingests YOLO output as evidence layer | We're the downstream consumer — not duplicating SIH26012 |
| GeoJSON/SHP/GeoTIFF/Parquet | ✅ Multi-format adapter (GeoJSON, SHP, GPKG, GeoParquet, CSV, GeoTIFF) | Full format coverage |
| Encroachment detection | Ripple check: building, utility, ROW | With auto-approval gates |
| NAKSHA workflow | Designed to sit *alongside* NAKSHA as a reconciliation layer | Complementary, not competing |

### Flugelsoft Gap Analysis

| Flugelsoft Feature | GeoSamanvay Equivalent | Our Advantage |
|---|---|---|
| Conflict queue | ✅ Priority-scored review queue | With provenance-aware priority scoring |
| AI boundary snap | Minimum-change proposal (no silent snap) | Explained proposal, not black-box |
| Confidence score | ✅ Per-signal confidence breakdown | Explainable, not a magic number |
| Auto-resolution | ✅ Gated auto-approve (5 criteria must pass) | Topology/ripple gates prevent unsafe auto-approval |
| Multi-source ingestion | ✅ Full multi-format adapter | Same |

---

## 3. Our Genuine Differentiators

### 3.1 Provenance-Aware Independence (unique to GeoSamanvay)

**The problem**: 4 datasets agreeing is meaningless if 3 descend from the same survey.

```
Cadastral Map (2019)
        ↓
Municipal GIS Export
        ↓
Tax Database
        ↓
Utility Records

= 4 datasets, but only 1 independent origin
```

Our provenance DAG traces lineage to count *origins*, not files. This is a distinct technical idea not prominently featured in any public competitor.

**Result**: `independent_lineages=1` vs `source_count=4` — the match evidence is very different.

### 3.2 Minimum-Change Reconciliation (explicit principle)

We don't average, warp, or snap. We generate the *smallest defensible change* using source quality weights:

```
GNSS RTK        weight=1.00  →  reference geometry
Drone ORI       weight=0.92  →  slight adjustment
Municipal GIS   weight=0.70  →  0.8m adjustment required
Cadastral       weight=0.80  →  unchanged (already agrees with drone)
```

Every adjustment is documented with: why, which sources, what weight, what changed.

### 3.3 Ripple-Effect Validation before Auto-Approval

Before any proposal can be auto-approved, 5 gates must pass:
1. Match confidence ≥ 0.82
2. Boundary offset ≤ 2.0m
3. Area change ≤ 5%
4. ≥ 2 independent source lineages
5. Ripple check: no neighbor overlap, building conflict, utility crossing, or ROW encroachment

If any gate fails → `REVIEW_REQUIRED`. If critical topology conflict → `BLOCKED`.

**Demo moment**: Judge asks "why didn't you auto-approve this?" System answers with specific gate failure and downstream impact.

### 3.4 Explainable Confidence (breakdown, not badge)

Not: `Confidence: 94%`

Instead:
```
Signal          Score    What it means
Geometry         91%     IoU=0.97, boundary offset 1.42m
Identifier      100%     Khasra 1042 exact match
Attribute        86%     Owner name 94% similar (transliteration)
Temporal         88%     2021 vs 2024, 3yr gap
Provenance      100%     3 independent origins confirmed
─────────────────────────────────────────────────
Overall          93%     (weighted composite)
```

### 3.5 Immutable Sources + Versioned Proposals

Original data is never modified. The harmonization is a proposal:

```
SOURCE DATA (SHA-256 hashed, locked)
       ↓
HARMONIZATION PROPOSAL v1
       ↓
REVIEW / APPROVE / REJECT
       ↓
VERSIONED OUTPUT (new record)
       ↓
Ed25519 SIGNED EVIDENCE PACKAGE
```

Every decision is cryptographically signed and independently verifiable.

### 3.6 Change Detection: Temporal vs. Concurrent

We distinguish:
- **BOUNDARY_DRIFT**: consistent 1-2m offset = likely datum shift, not conflict
- **GEOMETRY_CHANGE**: genuine boundary change over time (temporal evolution)
- **CONCURRENT_CONFLICT**: same-era sources disagree = actual error

This prevents false alarms on decade-old vs. current surveys.

---

## 4. What We Explicitly Do NOT Build (Strategic Scoping)

| Feature | Reason |
|---|---|
| AI boundary segmentation from raw imagery | SIH26012 territory; we *consume* extracted features |
| 3D building extrusion / digital twin | A.L.I.G.N. already has this; not core to reconciliation |
| Citizen land portal / property search | SIH26014 direction |
| NAKSHA replacement | We sit alongside NAKSHA as a reconciliation layer |
| Aadhaar/identity data integration | PII risks; not required for parcel reconciliation |
| Cloud-only deployment | Offline-first is our design principle |

---

## 5. Government Context Positioning

The correct narrative is NOT "government has disconnected land systems."

It IS: "Government has multiple valuable land-data systems generating increasingly rich datasets. The remaining challenge is reconciling differences between them."

```
NAKSHA            ← urban GIS, aerial/drone survey, ORI
Bhu-Naksha        ← cadastral map management, RoR integration
ULPIN/Bhu-Aadhaar ← parcel identification
DILRMP            ← digitization, georeferencing, map-RoR linkage

         ↓ all feed into ↓

      GeoSamanvay
      ─────────────────────────────────
      When these datasets disagree:
      • Which records are independent?
      • What is the conflict?
      • What is the minimum safe change?
      • What does it affect?
      • Who approved it, and why?
```

**The pitch**: "ULPIN identifies the parcel. GeoSamanvay reconciles the evidence describing that parcel."

---

## 6. Claims Matrix

| Claim | Status | Evidence |
|---|---|---|
| Multi-source parcel matching | ✅ Implemented | matching/matcher.py, 62+ tests |
| Provenance-aware independence | ✅ Implemented | core/provenance.py |
| Minimum-change harmonization | ✅ Implemented | harmonization/proposer.py |
| Topology/ripple validation | ✅ Implemented | topology/ripple_check.py |
| Multilingual owner matching | ✅ Implemented | matching/multilingual.py |
| ULPIN generation (DoLR spec) | ✅ Implemented | core/ulpin.py |
| Multi-format ingestion | ✅ Implemented | ingestion/format_adapters.py |
| Change detection engine | ✅ Implemented | core/change_detection.py |
| Imagery-derived feature adapter | ✅ Implemented | ingestion/imagery_adapter.py |
| Before/after map comparison | ✅ Implemented | frontend/BeforeAfterMap.tsx |
| OGC API Features output | ✅ Implemented | export/ogc_api.py + routes_v2.py |
| GeoPackage export | ✅ Implemented | export/ogc_api.py |
| Ed25519 signed evidence | ✅ Implemented | core/signing.py + evidence_envelope.py |
| Offline-first deployment | ✅ Docker Compose, SQLite | Dockerfile, docker-compose.yml |
| Original data immutable | ✅ Architectural principle | Source records never modified |

**Claims we do NOT make**:
- ❌ Creates authoritative land records
- ❌ Eliminates land disputes
- ❌ AI determines the correct boundary
- ❌ Replaces NAKSHA/Bhu-Naksha/ArcGIS
- ❌ 100% accurate
- ❌ Government-ready nationwide

---

## 7. Demo Storyboard (SIH Presentation)

**One ward. One conflicting parcel. One complete workflow.**

```
Scene 1 — Import (30s)
  Load 4 source datasets: Cadastral, Revenue/RoR, Municipal GIS, Drone ORI
  System profiles quality, normalizes CRS, hashes each record

Scene 2 — System matches (20s)
  "4 records → Parcel P-1042"
  Match confidence: 93%
  Independent lineages: 2 (Revenue shares origin with Cadastral)

Scene 3 — Conflicts shown (30s)
  🔴 Boundary offset: 1.42m (Cadastral vs Drone)
  🟠 Area mismatch: 2.1% (Municipal vs others)
  🟡 Owner spelling: "Ramesh Kumar" vs "Ramesh K. Kumar"

Scene 4 — Confidence explainer (20s)
  Click each signal to see why the score is what it is

Scene 5 — Minimum-change proposal (20s)
  "Drone ORI boundary used as reference (weight=0.92)"
  "Municipal boundary requires 0.8m adjustment"

Scene 6 — Ripple check BLOCKS auto-approve (30s)
  Building footprint crosses proposed municipal boundary
  → REVIEW REQUIRED

Scene 7 — Officer reviews + approves (20s)
  Review panel shows priority, reason, conflicts
  Officer enters justification → APPROVED

Scene 8 — ULPIN generated (10s)
  14-digit ULPIN assigned from centroid

Scene 9 — Evidence exported (10s)
  ZIP + GeoPackage downloaded
  SHA-256 manifest, Ed25519 signature, full audit trail

Total: ~3 minutes
```

---

## 8. Technical Spec Summary

**Backend**: Python 3.11 / FastAPI / SQLAlchemy / SQLite→PostGIS  
**Geospatial**: Shapely / PyProj / rtree / GeoPandas / Fiona  
**ML**: RapidFuzz (attribute matching) — LightGBM optional  
**Crypto**: Ed25519 (cryptography) / SHA-256  
**Frontend**: React 18 / TypeScript / MapLibre GL JS  
**Standards**: OGC API Features / GeoPackage (OGC 12-128r18) / W3C PROV-inspired  
**Tests**: 62+ passing (unit + integration)  
**Deployment**: Docker Compose, offline-capable  

---

*GeoSamanvay — Team Aikta — SIH26013 — 2026*
