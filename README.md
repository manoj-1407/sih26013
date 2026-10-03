# GeoSamanvay
**Evidence-Aware Multi-Source Geospatial Harmonization**
SIH26013 · Smart India Hackathon 2026 · Team Aikta

---

> When different land records disagree about the same parcel, GeoSamanvay
> determines which sources are independent, explains the conflict, proposes
> the smallest defensible change, checks its impact on surrounding features,
> and preserves the complete evidence chain behind every decision.

```
INGEST → PROFILE → MATCH → EXPLAIN → PROPOSE → VALIDATE → REVIEW → PUBLISH
```

**Core principle: Never overwrite sources. Reconcile them.**

---

## Quickstart

### Option 1: Docker (recommended)
```bash
git clone <repo>
cd sih26013_latest
docker compose up
# → http://localhost:8013
# → http://localhost:8013/docs  (interactive API)
```

### Option 2: Local Python
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8013 --reload
```

### Load the Ward 42 demo (one click)
```bash
# Via API:
curl -X POST http://localhost:8013/api/v1/demo/load-ward42
# Or click "Load Ward 42 Demo" in the UI Cases tab
```

This ingests 4 source datasets with known conflicts on Parcel P-1042,
runs the full harmonization pipeline, and populates the review queue.

---

## The Problem

A single urban parcel — four government records:

| Source | Area | Issue |
|---|---|---|
| Cadastral 2019 | 1,245 m² | Legacy survey, 1.4m NE corner offset |
| Revenue / RoR | 1,238 m² | Shares cadastral origin |
| Municipal GIS | 1,219 m² | Newer digitization, narrower boundary |
| Drone ORI 2024 | 1,231 m² | Most accurate, 0.15m GSD |

Plus: building footprint crosses boundary, drainage crosses NE corner.

**The naive system:** "Let's snap everything to the drone boundary."  
**Our system:** "Which of these are actually independent? What breaks if we move the boundary? Who approved it?"

---

## Eight-Layer Architecture

```
Layer 1  Data Connector + Ingestion
         GeoJSON · Shapefile · GeoPackage · GeoParquet · CSV · GeoTIFF

Layer 2  Normalization + Quality
         CRS · schema · geometry repair · units · timestamps · SHA-256

Layer 3  Canonical Parcel Model
         Parcel identity · source references · lineage · versions

Layer 4  Intelligent Matching Engine
         Geometry(35%) + Identifier(25%) + Attributes(15%) + Temporal(10%) + Provenance(15%)

Layer 5  Conflict + Harmonization Engine
         Taxonomy · minimum-change proposal · attribute reconciliation

Layer 6  Topology + Ripple Validation
         Neighbors · buildings · utilities · roads/ROW · auto-approval gates

Layer 7  Review + Versioned Decision
         Priority queue · officer approve/reject · Ed25519 signed decision

Layer 8  Provenance + Evidence + Interoperability
         Lineage graph · audit trail · GeoPackage · OGC API Features-aligned
```

---

## Four Genuine Differentiators

### 1. Provenance-Aware Independence
Three datasets from the same 1999 survey = **one** independent observation, not three.
The DFS lineage graph counts origins, not files.

```
ORIG-SURVEY-1999 → Cadastral → Revenue   }  one lineage
ORIG-AERIAL-2022 → Municipal             }  second lineage
ORIG-DRONE-2024  → Drone ORI             }  third lineage
                                            = 3 independent, not 4
```

### 2. Minimum-Change Reconciliation
Not averaging. Not snapping. The smallest defensible change:
- Highest-quality source (drone, weight=0.92) as geometry reference
- Only adjust sources that differ beyond tolerance
- Every adjustment documented with why, which source, what weight

### 3. Ripple-Effect Validation
Before any proposal is auto-approved, 5 gates + a ripple check must pass:
```
Proposed: P-1042 boundary shift 0.8m

Ripple check:
  P-1041  ✓ unaffected
  P-1043  ⚠ 0.31m² overlap INTRODUCED  → BLOCKS auto-approve
  Building ⚠ 2.1m² outside new boundary → BLOCKS auto-approve
  Road ROW ✓ unaffected (12m+ clearance)
  Drain    ⚠ new crossing               → MEDIUM severity

DECISION: REVIEW REQUIRED
```
High confidence (93%) does not override topology constraints.

### 4. Signed Evidence Package
Every decision:
```
decision.json + source_manifest.json + conflicts.json + confidence.json
+ validation.json + audit.jsonl + manifest.sha256
→ Ed25519 signed · independently verifiable · no server call required
```

### 5. 60-Second Judge Demo Path
Open the app → Demo tab → Start Demo → three sequential moments:
- Parcel 1042: 4 conflicting sources, ripple blocks auto-approval with specific reasons
- Provenance: 4 files → 3 origins → independence scores shown live
- Tamper: sign → mutate one field → verify → TAMPER DETECTED

### 6. RBAC + Audit Governance
Every approve/reject requires REVIEWER or APPROVER role. Decisions are Ed25519-signed and hash-chained in the audit trail. A field officer in 2035 can verify a 2026 decision with no server connection.

---

## API Reference

All endpoints at `/api/v1/`. Interactive docs at `/docs`.

| Method | Endpoint | Description |
|---|---|---|
| POST | `/demo/load-ward42` | One-click Ward 42 demo setup |
| GET | `/demo/status` | Which demo cases are loaded |
| GET | `/demo/provenance-demo` | Independence analysis scenarios (3 cases) |
| GET | `/demo/signed-envelope` | Fetch signed envelope for tamper demo |
| GET | `/demo/crs-demo` | CRS normalisation gate demonstration |
| GET | `/demo/benchmark` | Benchmark results + matching signal weights |
| GET | `/health` | System status |
| POST | `/cases` | Create a case |
| GET | `/cases/{id}` | Case detail + stats |
| POST | `/cases/{id}/datasets` | Ingest source dataset (JSON body) |
| POST | `/cases/{id}/datasets/upload` | File upload (SHP/GPKG/GeoParquet/CSV) |
| POST | `/cases/{id}/provenance/nodes` | Register provenance node |
| POST | `/cases/{id}/harmonize` | Run full pipeline |
| GET | `/cases/{id}/parcels` | List canonical parcels |
| GET | `/cases/{id}/parcels/{pid}` | Parcel detail + conflicts + proposal |
| GET | `/cases/{id}/parcels/{pid}/sources` | Source geometries (for before/after map) |
| GET | `/cases/{id}/parcels/{pid}/diff` | Harmonization diff |
| GET | `/cases/{id}/parcels/{pid}/ulpin` | ULPIN from authoritative source or demo id |
| GET | `/cases/{id}/parcels/{pid}/export` | Evidence ZIP download |
| POST | `/cases/{id}/proposals/{pid}/decide` | Officer approve/reject |
| POST | `/cases/{id}/proposals/{pid}/request-survey` | Request field verification |
| GET | `/cases/{id}/review` | Officer review queue |
| GET | `/cases/{id}/quality-report` | Data quality summary |
| GET | `/cases/{id}/change-detection` | Temporal change analysis |
| GET | `/cases/{id}/audit` | Audit trail |
| GET | `/cases/{id}/export/geopackage` | GeoPackage download |
| GET | `/cases/{id}/export/geojson` | GeoJSON export |
| GET | `/cases/{id}/ogc/collections` | OGC API Features collections |
| GET | `/cases/{id}/ogc/collections/{cid}/items` | Paginated features |
| POST | `/verify` | Verify signed evidence envelope |
| POST | `/names/compare` | Multilingual owner name comparison |
| POST | `/ulpin/validate` | Validate ULPIN format |
| GET | `/formats` | Supported ingestion formats |

---

## Supported Ingestion Formats

| Format | Extension | Notes |
|---|---|---|
| GeoJSON | `.geojson`, `.json` | Native, always supported |
| Shapefile | `.shp` (+ sidecar files or ZIP) | Requires `fiona` |
| GeoPackage | `.gpkg` | Requires `fiona`; layer selection supported |
| GeoParquet | `.parquet` | Requires `geopandas` |
| CSV | `.csv` | Auto-detects lat/lon or WKT column |
| GeoTIFF | `.tif`, `.tiff` | Spatial extent + metadata extracted |
| ZIP archive | `.zip` | Auto-extracts any of the above |

---

## Technology Stack

| Layer | Stack |
|---|---|
| Backend | Python 3.11 · FastAPI · Pydantic v2 · SQLAlchemy 2 |
| Geospatial | Shapely · PyProj/PROJ · rtree · GeoPandas · Fiona |
| Database | SQLite → PostGIS (swap via DATABASE_URL) |
| Matching | RapidFuzz · deterministic weighted scorer |
| Crypto | Ed25519 (cryptography) · SHA-256 |
| Frontend | React 18 · TypeScript · MapLibre GL JS · TanStack Query |
| Standards | OGC API Features-aligned · OGC GeoPackage · W3C PROV-inspired |
| Testing | pytest · httpx TestClient · 183 tests |
| Deployment | Docker Compose · offline-capable · no cloud dependency |

---

## Test Coverage

```
Unit tests (121):
  Geometry validation, IoU, Hausdorff, CRS plausibility,
  provenance independence, schema normalization, ULPIN validation,
  multilingual matching, change detection, ripple check, evidence signing

Integration tests (62):
  Full API lifecycle, Ward 42 E2E (20 tests), security audit (29 tests)

Run all tests:
  cd backend && python -m pytest tests/ -v
```

---

## Benchmarks (synthetic controlled corpus)

| Test | Result | Conditions |
|---|---|---|
| Ingest throughput | ~3,500 rec/s | SQLite, single process |
| Spatial index query p50 | ~0.07ms | R-tree, 100K parcels |
| Candidate reduction | ~463,000× | vs O(N²) naive pairing |
| Conflict detection | 100% | Injected pairs with 80m+ offset |
| Ed25519 signing p50 | ~0.16ms | Fixed payload |

*All benchmarks on synthetic random parcels. Real-world performance varies.*

---

## Claims Matrix

| Claim | Status |
|---|---|
| Multi-source parcel matching (geometry + identifier + attribute + temporal + provenance) | ✅ |
| Provenance-aware independence counting | ✅ |
| Minimum-change harmonization proposal | ✅ |
| Topology + ripple validation before auto-approval | ✅ |
| Multilingual owner name matching (Devanagari ↔ Roman) | ✅ |
| ULPIN validation + linking from authoritative sources | ✅ |
| Multi-format ingestion (GeoJSON/SHP/GPKG/GeoParquet/CSV) | ✅ |
| Ed25519 signed, independently verifiable decisions | ✅ |
| RBAC enforcement (REVIEWER/APPROVER required for proposal decisions) | ✅ |
| Administrative boundary crossing detection (ripple) | ✅ |
| Immutable source records throughout | ✅ |
| OGC API Features-aligned interface | ✅ |
| GeoPackage export (opens in QGIS/ArcGIS) | ✅ |
| Offline-first deployment | ✅ |

**Not claimed:**
- ❌ "AI determines the correct boundary" (AI assists matching; rules constrain)
- ❌ "ULPIN generated per DoLR algorithm" (we consume authoritative ULPINs)
- ❌ "OGC CITE certified" (aligned, not formally tested)
- ❌ "Production-scale 100K" (synthetic benchmark only)
- ❌ "Replaces NAKSHA/Bhu-Naksha" (reconciliation layer alongside them)

---

## Government Integration Positioning

```
NAKSHA / BhuNaksha / DILRMP / State Systems
                    ↓ outputs
              GeoSamanvay
         reconciliation layer
                    ↓ proposals
     Harmonized + evidence-backed records
                    ↓ approved by officer
         Back to government systems
```

"ULPIN identifies the parcel. GeoSamanvay reconciles the evidence describing it."

---

## Limitations

- Matching confidence is a weighted signal, not a calibrated probability
- Minimum-change geometry uses source quality weights, not a constrained optimization solver
- DSM/DTM elevation values are not analyzed (spatial extent only)
- GNSS accuracy modeling is not implemented (CSV lat/lon accepted)
- OGC CITE conformance testing not yet performed
- ML matching model (LightGBM) requires a labelled corpus to activate; rule-based scoring is the production default
- CV/ORI boundary extraction is consumed as input, not generated

---

## License

MIT · *SIH26013 · Team Aikta · 2026*
