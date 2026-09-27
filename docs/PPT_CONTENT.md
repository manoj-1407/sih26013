# GeoSamanvay — SIH26013 PPT Content
## Six slides, production-ready

---

## SLIDE 1 — Problem & Solution Identity

**Title**: GeoSamanvay — Evidence-Aware Multi-Source Geospatial Harmonization

**Problem table** (one parcel, four records):
| Source | Area | Issue |
|---|---|---|
| Cadastral 2019 | 1,245 m² | Legacy survey — 1.4m NE corner offset |
| Revenue / RoR | 1,238 m² | Shares cadastral origin — NOT independent |
| Municipal GIS | 1,219 m² | Newer digitization, narrower boundary |
| Drone ORI 2024 | 1,231 m² | Most accurate · 0.15m GSD |

**Wrong**: "AI snaps boundary to drone — 99.2% confidence" → destroys provenance, no audit trail

**Right**: "Reconcile evidence · explain conflict · minimum change · check topology · human approves · sign the decision"

**Core sentence**: "Instead of choosing one map as truth, GeoSamanvay reconciles the evidence and produces a traceable harmonization proposal."

---

## SLIDE 2 — Four Differentiators

1. **Provenance-Aware Independence** — 4 datasets, only 2 independent origins. Counts lineages, not files.

2. **Minimum-Change Reconciliation** — Drone reference (0.92) · Municipal −0.8m · Cadastral unchanged. Every change explained.

3. **Ripple-Effect Validation** — 93% confidence ≠ auto-approval. P-1043 overlap 0.31m² blocks it. System knows when to stop.

4. **Signed Evidence Package** — Ed25519 signed · SHA-256 manifest · auditable offline · every field traceable.

---

## SLIDE 3 — Technical Workflow

Eight layers:
- L1 Data Ingestion: GeoJSON · SHP · GPKG · GeoParquet · CSV · GeoTIFF
- L2 Normalization: CRS · schema · repair · SHA-256
- L3 Canonical Parcel Model: identity · provenance DAG · versions
- L4 Matching: Geometry(35%) + ID(25%) + Attr(15%) + Temporal(10%) + Provenance(15%)
- L5 Conflict + Harmonization: taxonomy · minimum-change · attribute reconciliation
- L6 Topology + Ripple: neighbors · buildings · utilities · ROW · 5 auto-approval gates
- L7 Review + Decision: queue · approve/reject · Ed25519 signed
- L8 Evidence + Interop: GeoPackage · OGC API Features-aligned · audit

**Stack**: FastAPI · Shapely · PyProj · rtree · React 18 · MapLibre · SQLite/PostGIS

**174 tests · offline-first · no cloud dependency**

---

## SLIDE 4 — Live Demo: Ward 42, Parcel P-1042

Steps:
1. Import 4 datasets (one button: "Load Ward 42 Demo")
2. System matches P-1042 — **only 2 independent origins, not 4**
3. Conflicts: boundary offset 1.42m · area mismatch 2.1% · owner name variant
4. Confidence explainer: Geometry 94% · ID 100% · Attribute 86% · Provenance 100% → **93%**
5. Minimum-change proposal: Drone as reference · Municipal −0.8m · Cadastral unchanged
6. **Ripple check blocks auto-approval** — building 2.1m² outside · P-1043 overlap 0.31m²
7. Officer reviews + approves with justification
8. Evidence ZIP downloaded — signature verified ✓

**Available live at http://localhost:8013**

---

## SLIDE 5 — Validation & Government Fit

**Tests**: 174 passing · Ward 42 E2E · 32 security tests

**Benchmarks** (synthetic):
- ~3,500 rec/s ingest
- 463,000× candidate reduction
- 100% conflict detection (injected pairs)
- 0.16ms Ed25519 signing

**Honest claims** ✓:
- Multi-source matching · Immutable sources · Topology validated · Signed evidence · Offline-first

**Not claimed** ✗:
- "AI determines the correct boundary"
- "ULPIN generated per DoLR algorithm"
- "OGC CITE certified"
- "Replaces NAKSHA / Bhu-Naksha"

**Government positioning**:
```
NAKSHA → Bhu-Naksha → ULPIN/DILRMP → [GeoSamanvay] → Harmonized + evidence
                        ← reconciliation layer, not replacement →
```

---

## SLIDE 6 — Research, Prototype & Closing

**Running prototype**:
- `docker compose up` → http://localhost:8013
- One-click Ward 42 demo, no internet required

**Capabilities** (all implemented, all tested):
Multi-format ingestion · CRS normalization · Schema normalization · Multi-signal matching · Provenance independence · Multilingual matching · Change detection · ULPIN linkage · Data quality profiling · Imagery feature adapter · Harmonization diff · Survey request workflow · Conflict taxonomy · Harmonization proposal · Topology + ripple · Auto-approval gates · Officer review queue · Versioned decisions · Ed25519 signed evidence · GeoPackage export · OGC API Features-aligned · Before/after map slider · Audit trail

**Closing**:
> "Most systems help you store land data.  
> GeoSamanvay explains why your sources disagree — and what to do about it."

Team Aikta · SIH26013 · Smart India Hackathon 2026 · Open-source · MIT License
