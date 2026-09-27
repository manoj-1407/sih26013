# GeoSamanvay — Complete Product Strategy Freeze
## SIH26013 · Team Aikta · September 2026
### Based on: 122-test build + competition research + requirements audit

---

> This document supersedes all earlier strategy notes. It is the single
> source of truth for what we build, what we demo, what we claim, and what
> we do not touch. Nothing new is added to the codebase until this document
> authorizes it.

---

## A. PS26013 Requirement → Exact Implementation Mapping

The official PS26013 requirement categories mapped to our modules:

### A1. Multi-Source Data Integration

| PS Requirement | Our Module | Status |
|---|---|---|
| Cadastral maps | `ingestion/ingestor.py` + `format_adapters.py` | ✅ |
| Revenue/RoR records | Same, SourceType.REVENUE_ROR | ✅ |
| Municipal GIS | Same, SourceType.MUNICIPAL_GIS | ✅ |
| Drone / ORI | `ingestion/imagery_adapter.py` + SourceType.DRONE_ORI | ✅ |
| DSM / DTM | `format_adapters.from_geotiff_metadata` (metadata only) | ⚠ |
| Utility networks | SourceType.UTILITY_NETWORK + ripple check | ✅ |
| Building footprints | SourceType.BUILDING_FOOTPRINT + imagery adapter | ✅ |
| GNSS / CORS | SourceType.GNSS_SURVEY (CSV ingestion path) | ⚠ |
| Historical records | SourceType.HISTORICAL (lower quality weight) | ✅ |
| Multi-format ingestion | GeoJSON, SHP, GPKG, GeoParquet, CSV, GeoTIFF | ✅ |

### A2. Spatial + Attribute Processing

| PS Requirement | Our Module | Status |
|---|---|---|
| CRS transformation + recording | `core/crs_check.py`, `core/geometry.py` | ✅ |
| Geometry validation + repair | `core/geometry.py` (make_valid) | ✅ |
| Schema normalization | `ingestion/schema_normalizer.py` (60+ aliases) | ✅ |
| Multilingual attribute matching | `matching/multilingual.py` | ✅ |
| Area unit normalization | `ingestion/schema_normalizer.py` | ✅ |

### A3. Matching + Conflict

| PS Requirement | Our Module | Status |
|---|---|---|
| Spatial matching | `matching/matcher.py` (IoU + Hausdorff) | ✅ |
| Identifier matching | Same (Khasra/ULPIN/property ID) | ✅ |
| Attribute matching | Same + multilingual module | ✅ |
| Temporal change detection | `core/change_detection.py` | ✅ |
| Conflict detection | `conflicts/detector.py` (full taxonomy) | ✅ |
| Topology correction | `topology/ripple_check.py` | ✅ |
| Confidence scoring | `matching/matcher.py` (per-signal, 5 components) | ✅ |

### A4. Governance + Output

| PS Requirement | Our Module | Status |
|---|---|---|
| Harmonization proposal | `harmonization/proposer.py` | ✅ |
| Human review workflow | `review/queue.py` + ReviewPanel.tsx | ✅ |
| Versioned output | DBProposal.version + decision store | ✅ |
| Audit trail | DBAuditEvent + SHA-256 event hash | ✅ |
| Evidence package | `export/package_exporter.py` (ZIP + manifest) | ✅ |
| GeoPackage export | `export/ogc_api.py` | ✅ |
| OGC API Features interface | `api/routes_v2.py` (aligned, not CITE-certified) | ⚠ |
| ULPIN integration | `core/ulpin.py` (consume + validate + link) | ✅ |

---

## B. Competitor Capability Matrix

Based on verified public material only. No invented capabilities.

| Capability | A.L.I.G.N. | Flugelsoft | GeoSamanvay |
|---|---|---|---|
| Multi-source data ingestion | ✓ | ✓ | ✓ |
| Spatial matching | ✓ | ✓ | ✓ |
| Attribute / owner matching | ✓ | ✓ | ✓ |
| Multilingual names | ✓ (IndicSoundex) | ✓ | ✓ |
| Conflict detection + queue | ✓ | ✓ | ✓ |
| Confidence score | limited public detail | 99.2% shown | ✓ per-signal breakdown |
| AI boundary correction | ✓ (TPS warp) | ✓ (snap to drone) | ✗ intentionally |
| 3D visualization | ✓ | ✗ | ✗ intentionally |
| ULPIN-related | ✓ | ✗ | ✓ (consume + link) |
| Before/after map | ✓ | partial | ✓ (slider) |
| Provenance lineage tracking | ✗ not prominent | ✗ | ✓ |
| Independent-origin counting | ✗ | ✗ | ✓ |
| Minimum-change proposal | ✗ | ✗ | ✓ |
| Ripple/topology auto-gate | ✗ | ✗ | ✓ |
| Immutable source records | ✗ | ✗ | ✓ |
| Versioned harmonization | ✗ | ✗ | ✓ |
| Ed25519 signed evidence | ✗ | ✗ | ✓ |
| Reproducible proposal | ✗ | ✗ | ✓ |
| Honest claims / disclaimers | limited | limited | ✓ explicit |
| Offline-first deployment | ✗ | cloud-first | ✓ (Docker, SQLite) |

**Reading**: The first three columns are approximately the same. The last 10 rows are where we are distinct. That's the story.

---

## C. "Everyone Will Probably Build This" — Do Not Make This Our Differentiator

Any serious SIH26013 team will likely implement these. They are necessary but not sufficient:

1. **GeoJSON ingestion + map display** — every team has this
2. **Spatial overlap detection** — trivial with Shapely/GeoPandas
3. **Attribute fuzzy matching** — RapidFuzz is a one-liner
4. **Confidence score** — every team will print a percentage
5. **Conflict queue / dashboard** — standard CRUD
6. **Before/after map toggle** — visual, easy to add
7. **Encroachment detection** — building outside parcel is simple topology
8. **Multi-source overlay map** — standard MapLibre layer management
9. **FastAPI backend + React frontend** — standard template
10. **ULPIN display** — showing a number is trivial

**Conclusion**: If our demo story is "we detect conflicts and show a confidence score," we are describing every competitor. The judges may have already seen exactly this flow.

---

## D. Our Genuine Differentiators — The Four Ideas Worth Defending

These are the things public competitors do not prominently feature and that are technically grounded.

### D1. Provenance-Aware Independence (not just source count)

**What we do**: DFS lineage graph traces each record to its origin node. Multiple records from the same survey count as *one* independent observation, not multiple votes.

**Why it matters**: A naive system claims "4 sources agree — high confidence." Our system can say "4 sources, but 2 share a common 1999 survey origin — only 2 independent observations." This directly changes the confidence interpretation.

**Demo moment**: Show Cadastral → Revenue → both trace to ORIG-SURVEY-1999. Then show the confidence panel showing "2 independent lineages" not "4 sources."

**Claim**: "We count independent origins, not file count. Three datasets from the same survey are one observation."

### D2. Minimum-Change Reconciliation (not averaging, not overwriting)

**What we do**: Source quality-weighted geometry selection — highest-quality source is the reference; others require adjustment only as needed. Attribute reconciliation uses weighted voting. Neither operation modifies source records.

**Why it matters**: Competitors snap to drone (AI-authoritative) or average boundaries (mathematically convenient but defenseless). We can explain every change: "This vertex moved 0.72m because 3 of 4 independent sources support this position."

**Demo moment**: Show the change summary: "Drone ORI reference (weight=0.92), Municipal requires 0.8m adjustment, Cadastral unchanged."

**Claim**: "We propose the smallest defensible change, not the AI's preferred boundary."

### D3. Ripple-Aware Auto-Approval Gate

**What we do**: Before any proposal can be auto-approved, 5 gates must pass AND a ripple check must confirm no neighboring parcel overlap, no building-outside-parcel, no new utility crossing, no road ROW conflict is introduced.

**Why it matters**: Competitor systems auto-resolve at high confidence. Our system can show: "92% confident, but the proposed change creates a 0.31m² overlap with P-1043 — therefore NOT auto-approvable." This demonstrates the system knows when not to act.

**Demo moment**: Parcel P-1042 gets REVIEW_REQUIRED because the building crosses the new boundary. High confidence is not sufficient when topology fails.

**Claim**: "High confidence does not override spatial constraints. The system knows when to stop."

### D4. Reproducible, Signed Evidence Package

**What we do**: Every approved harmonization decision is cryptographically signed (Ed25519), SHA-256 hashed, and exported as a self-contained ZIP with source manifest, conflicts, confidence breakdown, validation result, audit trail, and manifest checksum.

**Why it matters**: Competitors produce harmonized maps. We produce a verifiable proof of *why* the map changed. Any government auditor can verify the signature without calling our server.

**Demo moment**: Paste the decision.json into the Evidence tab — "Signature verified ✓ — Ed25519, KEY-GS-EXAMINER-26013-v1."

**Claim**: "Original data is never overwritten. Every decision is an independently verifiable proof of what changed, why, and who approved it."

---

## E. Features We Should NOT Build

Adding these would make the project worse, not better. Time is finite.

| Feature | Reason to Skip |
|---|---|
| Raw imagery segmentation (YOLO, SAM-2) | SIH26012 territory; we consume extracted outputs |
| 3D building extrusion / digital twin | A.L.I.G.N. already owns this visually; not core to reconciliation |
| Legal notice generation | Feature creep; out of scope for harmonization engine |
| Citizen land portal / property search | SIH26014 direction |
| Aadhaar / identity data integration | PII risks; not required; ethically sensitive |
| "AI determines the correct boundary" | Wrong framing; legally indefensible |
| More ML models (XGBoost, transformers) | We have no calibrated training data; deterministic scoring is more defensible |
| Cloud deployment / Kubernetes | Docker Compose is sufficient for SIH; adds complexity |
| Terrain / elevation analysis | DSM/DTM metadata extracted; elevation harmonization is a separate product |
| Survey measurement error modeling | Requires GNSS accuracy specifications we don't have |
| More tests to reach "200 tests" | Depth > quantity; fix the ⚠ items before adding new tests |

---

## F. 3–5 Killer Features Worth Adding (all are small)

These are the remaining high-value additions that can be done in 2–4 hours each:

### F1. Harmonization Diff View (HIGH PRIORITY)

The "Git diff for parcels" idea. Show exactly what changed between source state and proposal state.

```
PARCEL P-1042 — PROPOSED CHANGE DIFF
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GEOMETRY
  Boundary vertices: 8 total, 2 changed
  East edge:    − 1.42m  (cadastral offset removed)
  North edge:   − 0.72m  (aligned to drone reference)
  Other edges:  unchanged

AREA
  Before: 1,245 m² (cadastral)  1,219 m² (municipal)
  Proposed: 1,237 m² (−0.6% from cadastral, −1.5% from municipal)

ATTRIBUTES
  owner_reference: unchanged  ("Ramesh Kumar" — 94% match across sources)
  land_use: unchanged  (Residential — all sources agree)
  area_attribute: CONFLICT  (sources disagree — sent to review)

TOPOLOGY
  Neighbour P-1043: ⚠ 0.31m² overlap would be introduced
  Building BLD-1042: ⚠ extends 2.1m² beyond new boundary
  Road ROW: ✓ unaffected  (>12m clearance maintained)
  Drainage: ✓ unaffected

DECISION
  REVIEW REQUIRED — 2 topology issues
```

**Implementation**: New component `HarmonizationDiff.tsx` + API endpoint that computes the diff between source geometries and proposal geometry.

### F2. "Why Not Auto-Approved?" Explainer Screen (HIGH PRIORITY)

When a proposal is REVIEW_REQUIRED or BLOCKED, the officer should see a clear one-screen explanation:

```
WHY THIS PARCEL NEEDS REVIEW

✗ Gate 3 failed: Topology conflict introduced
  Building BLD-W42-1042 would extend 2.1m² outside proposed boundary

✗ Gate 5 failed: Ripple check
  Neighbor P-1043 overlap: 0.31m²

What the officer needs to decide:
  → Accept the overlap as within tolerance?
  → Request a new ground-truth survey?
  → Reject this proposal?
```

**Implementation**: Computed in `proposer.py` (already has `auto_reject_reasons`); display in `ReviewPanel.tsx`.

### F3. Ground-Truth Request Workflow (MEDIUM PRIORITY)

When an officer cannot decide from existing evidence, they should be able to issue:

```
REQUEST FIELD VERIFICATION
Parcel: P-1042
Required observation: Boundary point at NE corner
Current conflict: 1.42m discrepancy between cadastral and drone
Suggested method: GNSS/CORS RTK
Assigned to: Field Survey Team 4
```

When the GNSS observation comes back as a new GNSS_SURVEY source record, it re-triggers matching → conflict → proposal for that parcel.

**Implementation**: New `review_action = "REQUEST_FIELD_VERIFICATION"` in `routes.py`; simple DB field on DBProposal; display in ReviewPanel.

### F4. Data Quality Report (MEDIUM PRIORITY)

After ingestion, generate a printable summary:

```
DATASET QUALITY REPORT — Ward 42, Sept 2026
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Source           Records   Valid    Quality   Issues
─────────────────────────────────────────────────────
Cadastral 2019      10      10     HIGH 96%   0 CRS
Revenue RoR         10      10     HIGH 98%   0
Municipal GIS       10       9     MEDIUM 87% 1 invalid geom
Drone ORI           10      10     HIGH 99%   0
Buildings           10      10     HIGH 95%   0
─────────────────────────────────────────────────────
Total               50      49     GOOD       1 repaired

SHA-256 Manifest: [hash of all source records]
```

**Implementation**: Already exists in `quality_profiler.py` and `ingestion/ingestor.py`. Need a `/api/v1/cases/{id}/quality-report` endpoint and a simple `QualityReportPanel.tsx`.

### F5. Before/After Map — Wire Source Geometries (SMALL, HIGH IMPACT)

The `BeforeAfterMap.tsx` currently doesn't load real source geometries from the API in real time. Fix this: fetch the source records for the selected parcel from `/api/v1/cases/{id}/ogc/collections/{id}_source_records/items?parcel_id=...` and display them on the "before" side.

**Implementation**: Add `parcel_id` filter to the source records OGC endpoint; update `BeforeAfterMap.tsx` to fetch on `parcelId` prop change.

---

## G. Exact 3-Minute Judge Demo

**Setup**: One ward. One conflicting parcel. Every step is live, not mocked.

```
Time    Step                           What judge sees
──────────────────────────────────────────────────────────────────────────
0:00    Open the UI. Cases tab.        "GeoSamanvay. Evidence-Aware
                                        Geospatial Harmonization."

0:10    Create case WARD42-2026.       Case created. Active case shown
                                        in topbar.

0:20    Provenance tab. Show graph     "Three independent origins:
        pre-loaded for this demo.       1999 Survey, 2022 Aerial, 2024 Drone.
                                        Cadastral and Revenue share the 1999
                                        origin — they count as ONE observation,
                                        not two."

0:40    Ingest tab. Click              Quality profiles appear.
        "Load Ward 42 Demo".           "40 records, 4 source types ingested.
        [pre-loads all 5 datasets]      SHA-256 hash on every record.
                                        Source data is now locked."

1:00    Click Harmonize.               Stat panel: 40 records → 10 parcels,
                                        3 for review, 7 auto-approvable.

1:10    Map tab. Map loads.            10 parcels visible. Conflict parcels
                                        in amber/red. Click P-1042.

1:20    Info tab:                      "4 sources, 2 independent lineages.
        Match confidence: 93%           Not 4 — because Cadastral and Revenue
        Independent lineages: 2         share an origin."

1:35    Evidence tab:                  Per-signal bars animate in.
        Geometry 94% / ID 100% /        "Every number has a reason.
        Attribute 86% / Temporal 88% /  The 86% attribute score is because
        Provenance 100%                 the owner name differs by transliteration
                                        — 'Ramesh Kumar' vs 'Ramesh K. Kumar'."

1:55    Scroll to Proposal section:    "Drone ORI is the reference geometry
        "REVIEW REQUIRED"               — highest quality weight, 0.92.
                                        But the system blocked auto-approval."

2:05    Ripple Check callout:          "Building BLD-1042 extends 2.1m²
        ⚠ BUILDING_OUTSIDE              outside the new boundary.
        ⚠ Neighbor P-1043 overlap       Neighbor P-1043 would gain a 0.31m²
                                        overlap. The system checked the
                                        neighbourhood — not just this parcel."

2:20    Compare tab. Drag slider.      "Here are the four source boundaries.
                                        Here is the proposed boundary.
                                        The East edge moved 0.72m to align
                                        with the drone survey.
                                        Everything else unchanged."

2:35    Review Queue tab.              Priority 85 item for P-1042.
        Enter reason, click Approve.   "Officer approves with justification.
                                        Logged, timestamped, attributed."

2:50    Download Evidence ZIP.         "Source manifest. Conflicts. Confidence
        Paste decision.json in          breakdown. Ripple result. Signed
        Evidence verifier.             decision. SHA-256 manifest.
        "Verified ✓"                   Any auditor can verify this offline,
                                        without calling our server."

3:00    CLOSE.                         "Four sources disagreed.
                                        We explained why. Proposed the minimum
                                        safe change. Checked its impact.
                                        Let a human decide. Proved it happened."
```

---

## H. Exact Data Scenario — Ward 42, Parcel P-1042

**The protagonist parcel.** Everything below is deterministic in the demo data.

```
PARCEL: P-1042 (Ward 42, demo district, Maharashtra)

SOURCE RECORDS:
┌─────────────────┬──────────┬───────────────────────────────────────┐
│ Source          │ Area     │ Key difference                         │
├─────────────────┼──────────┼───────────────────────────────────────┤
│ Cadastral 2019  │ 1,245 m² │ NE corner offset +1.4m (legacy datum) │
│ Revenue RoR     │ 1,238 m² │ Shares cadastral origin               │
│ Municipal GIS   │ 1,219 m² │ Narrower boundary (26m vs 35m width)  │
│ Drone ORI 2024  │ 1,231 m² │ Most accurate; 0.15m GSD              │
└─────────────────┴──────────┴───────────────────────────────────────┘

PROVENANCE:
  ORIG-SURVEY-1999 → DS-CADASTRAL → Cadastral records
  ORIG-SURVEY-1999 → DS-REVENUE → Revenue records
  ORIG-AERIAL-2022 → DS-MUNICIPAL → Municipal records
  ORIG-DRONE-2024  → DS-DRONE → Drone records
  = 3 independent origins, not 4 datasets

CONFLICTS DETECTED:
  BOUNDARY_OFFSET  HIGH   1.42m  Cadastral vs Drone
  AREA_MISMATCH    MED    2.1%   Municipal vs others
  OWNER_MISMATCH   MED    94%    "Ramesh Kumar" vs "Ramesh K. Kumar"

CROSS-LAYER:
  Building BLD-W42-1042: footprint crosses municipal boundary by ~0.7m
  Drainage DRAIN-001: crosses NE corner

PROPOSAL:
  Reference geometry: Drone ORI (weight=0.92)
  Municipal requires: 0.8m boundary adjustment
  Cadastral: unchanged (already agrees with drone within tolerance)
  Decision: REVIEW_REQUIRED (building + neighbor issues)

RIPPLE:
  P-1043: 0.31m² overlap would be introduced → blocks auto-approve
  Building: 2.1m² outside new boundary → blocks auto-approve
  Road ROW: unaffected
  Drainage: new crossing introduced

RESOLUTION:
  Officer reviews. Approves with justification.
  Evidence package generated. SHA-256 signed.
```

This scenario is already encoded in `data/demo/ward42/`. The provenance graph is in `provenance_graph.json`.

---

## I. Final UI Structure

Seven tabs. Each has exactly one job.

```
┌────────────────────────────────────────────────────────────────────┐
│  GeoSamanvay          Case: WARD42-2026            ● Operational  │
├──────────┬─────────────────────────────────────────────────────────┤
│  CASES   │                                                          │
│  INGEST  │         [Main content panel — see below]                │
│  HARMON. │                                                          │
│  MAP ◄── │  ← Primary demo tab                                     │
│  REVIEW  │                                                          │
│  EVIDENCE│                                                          │
│  PROVNCE │                                                          │
└──────────┴─────────────────────────────────────────────────────────┘
```

### Tab: Map & Conflicts (primary demo view)

```
┌──────────────────────────────────┬─────────────────────────────────┐
│                                  │  P-1042                    [✕]  │
│         MapLibre GL               │  ┌──────────────────────────┐  │
│                                  │  │ INFO │ EVIDENCE │COMPARE │ULPIN│
│  [10 parcels visible]            │  └──────────────────────────┘  │
│  [amber = review required]       │                                  │
│  [red = blocked]                 │  INFO TAB                        │
│  [green = auto-approved]         │  Match: 93% · 2 lineages         │
│                                  │  4 sources · 1,237 m²            │
│                                  │  ──────────────────────────────  │
│                                  │  CONFLICTS (3)                   │
│                                  │  🔴 BOUNDARY_OFFSET 1.42m        │
│                                  │  🟠 AREA_MISMATCH 2.1%           │
│                                  │  🟡 OWNER_MISMATCH 94% sim       │
│                                  │  ──────────────────────────────  │
│                                  │  Proposal: REVIEW REQUIRED       │
│                                  │  Building outside boundary       │
│                                  │  [Evidence ZIP] [GeoPackage]     │
└──────────────────────────────────┴─────────────────────────────────┘
```

### Evidence tab (inside parcel panel)

```
Match Evidence Breakdown
  Geometry     ████████████░░ 94%  ⓘ IoU, Hausdorff, area ratio
  Identifier   ██████████████ 100% ⓘ Khasra exact match
  Attribute    ████████████░░ 86%  ⓘ Owner name 94% similar
  Temporal     █████████████░ 88%  ⓘ 2021 vs 2024, 3yr gap
  Provenance   ██████████████ 100% ⓘ 3 independent origins

2 independent source lineages
  [green banner] 2+ independent observations confirm this match.

Conflict Explanations
  [expandable cards for each conflict type with why-it-exists tooltip]

Harmonization Reasoning
  [REVIEW REQUIRED] Building outside boundary + neighbor overlap
  • Drone ORI boundary used as reference (weight=0.92)
  • Municipal boundary requires 0.8m adjustment
  • Max offset: 1.42m / Area change: 0.9%
  [Ripple: NOT SAFE — 2 blocking issues]
```

### Compare tab (before/after slider)

```
◀ BEFORE — Source Records    |    AFTER — Harmonization Proposal ▶
     [drag ⟺ slider divides map left/right]

"Original data is never overwritten."
```

### Review Queue tab

```
OFFICER REVIEW QUEUE
3 pending

P-1042  Priority 85  ●●●●○    [Review → Decide]
  REVIEW REQUIRED · 1 conflict · 2 ripple issues · 93% confidence

P-1038  Priority 42  ●●●○○    [Review → Decide]
  ...
```

---

## J. Final SIH PPT Story — 6 Slides

**Slide 1: The Problem**

Title: "Four government agencies surveyed the same parcel. They disagree."

Visual: Four overlapping polygon outlines of different colors, same parcel, clearly different boundaries.

Text:
- Cadastral: 1,245 m²
- Revenue: 1,238 m²  
- Municipal: 1,219 m²
- Drone 2024: 1,231 m²

"Which one is right? That's the wrong question."

---

**Slide 2: The Wrong Approach**

Title: "Existing solutions choose one source and overwrite the rest."

Visual: Arrow from 4 sources to 1 output, with a red ✗

- ✗ AI snaps boundary to drone edge (99.2% confidence)
- ✗ Average the polygons
- ✗ Newest source wins

"This destroys provenance. It makes the system the authority. Government can't audit or reverse it."

---

**Slide 3: Our Approach**

Title: "GeoSamanvay: Evidence-Aware Harmonization"

Visual: The 8-layer architecture diagram

"We don't choose one source. We reconcile the evidence across all sources and produce a traceable, reviewable proposal."

Core loop:
```
PROFILE → MATCH → EXPLAIN → PROPOSE → VALIDATE → REVIEW → VERSION
```

"Original data is never modified. Every decision is independently verifiable."

---

**Slide 4: The Four Ideas**

Title: "What makes this different"

2×2 grid:

**1. Independent Lineage**
"3 datasets from the same survey = 1 independent observation."

**2. Minimum-Change Proposal**  
"Smallest defensible change, not AI's preferred boundary."

**3. Ripple Check**
"High confidence doesn't override topology. If the change breaks a neighbor, it goes to review."

**4. Signed Evidence**
"Every decision is Ed25519-signed. Auditable offline. Reversible."

---

**Slide 5: Live Demo**

Title: "One parcel. Four conflicts. One traceable resolution."

Screenshot: Map tab with P-1042 selected, conflicts listed, Evidence panel showing per-signal breakdown, REVIEW REQUIRED with ripple issues visible.

"The system blocked auto-approval because the proposed boundary change would extend a building footprint outside the parcel. It explains why. It doesn't guess."

---

**Slide 6: Fit in the Ecosystem**

Title: "Not replacing NAKSHA. Sitting beside it."

Diagram:
```
NAKSHA / BhuNaksha / DILRMP / State Systems
                    ↓
              GeoSamanvay
         (reconciliation layer)
                    ↓
     Harmonized proposals with evidence
                    ↓
   Back to government systems + human review
```

"ULPIN identifies the parcel. GeoSamanvay reconciles the evidence about it."

"Open-source stack. Offline-capable. Standards-aligned. No cloud dependency."

---

## Freeze Rules

1. **No new features** until F1–F5 above are complete and tested.
2. **No PPT before** Ward 42 end-to-end demo runs cleanly in one pass.
3. **No claim** uses the word "conformant", "accurate", "AI determines", or "replaces".
4. **ULPIN** is always described as "validates and links authoritative ULPINs from source systems." Never "generates ULPIN per DoLR spec."
5. **Confidence scores** are always described as "weighted matching signal, not a calibrated probability."
6. **Benchmark numbers** are always qualified with "synthetic controlled benchmark."
7. **Every demo step** must work from the live API without mocking.

---

## Open Items Before Freeze (in priority order)

| # | Item | Effort | Priority |
|---|---|---|---|
| 1 | Wire Before/After map to real source geometries (F5) | 2h | P0 |
| 2 | Harmonization Diff component (F1) | 3h | P0 |
| 3 | "Why not auto-approved?" explainer (F2) | 1h | P0 |
| 4 | Run Ward 42 demo end-to-end via API; verify blocking ripple | 1h | P0 |
| 5 | Ground-truth request action (F3) | 2h | P1 |
| 6 | Quality report endpoint (F4) | 2h | P1 |
| 7 | Wire RBAC role checks to routes | 2h | P1 |
| 8 | Add DSM/DTM coverage display on map | 1h | P2 |

**Total remaining P0 effort: ~7 hours. P1: ~6 hours.**

After these are done, the product is complete. Do not add anything else.

---

*GeoSamanvay — Team Aikta — Product Strategy Freeze — September 2026*
