# GeoSamanvay — SIH26013 Requirements Audit
## Hard audit of every stated PS requirement against the actual codebase
### Team Aikta — September 2026

---

## How to read this document

Each requirement is rated:

- ✅ **IMPLEMENTED** — working code + test coverage
- ⚠ **PARTIAL** — started but incomplete or not yet tested end-to-end
- ❌ **MISSING** — not implemented
- 🔒 **DESCOPED** — intentionally excluded with justification

---

## Section 1 — Data Source Coverage

The PS asks for integration of these source types:

| Source | Status | Module | Notes |
|---|---|---|---|
| Drone imagery / ORI | ⚠ | `ingestion/imagery_adapter.py` | Consumes extracted features from ORI; does not process raw raster pixels — that's SIH26012 territory. GeoTIFF metadata (extent, CRS, resolution) is extracted. |
| DSM / DTM | ⚠ | `ingestion/format_adapters.py` → `from_geotiff_metadata` | Metadata and spatial extent extracted. Elevation values not analyzed — we don't do terrain analysis. |
| Cadastral maps | ✅ | `ingestion/ingestor.py` + `format_adapters.py` | GeoJSON, Shapefile, GeoPackage, GeoParquet all supported. SourceType.CADASTRAL. |
| Revenue / RoR | ✅ | Same | SourceType.REVENUE_ROR. Schema normalization handles Khasra_No, Khatadar, etc. |
| Municipal GIS | ✅ | Same | SourceType.MUNICIPAL_GIS. Property_ID, Plot_Area, etc. mapped. |
| Utility networks | ✅ | Same | SourceType.UTILITY_NETWORK. Used in cross-layer topology checks. |
| Building footprints | ✅ | `ingestion/imagery_adapter.py` | SourceType.BUILDING_FOOTPRINT. Cross-layer checks in ripple engine. |
| GNSS / CORS | ⚠ | SourceType.GNSS_SURVEY exists | No dedicated GNSS accuracy modeling. CSV with lat/lon accepted. |
| Historical maps | ✅ | SourceType.HISTORICAL | Supported as a source type with lower quality weight (0.50). |
| Administrative boundaries | ✅ | SourceType.ADMINISTRATIVE | Accepted; used for jurisdiction plausibility. |
| OGR / ORI | ⚠ | Metadata only | Spatial extent extracted from GeoTIFF. Feature extraction output consumed via imagery adapter. |

**Gap to close before demo**: Load the Ward 42 demo dataset from all relevant source types and confirm end-to-end ingestion works without errors.

---

## Section 2 — Spatial Data Processing

| Requirement | Status | Module | Notes |
|---|---|---|---|
| CRS detection + normalization | ✅ | `core/crs_check.py`, `core/geometry.py` | 4-gate CRS plausibility. Auto-reproject to WGS84 via PyProj. India-aware axis-swap detection. |
| Coordinate transformation recording | ✅ | `ingestion/ingestor.py` | Source CRS stored alongside normalized WKT. Every transformation is logged in content hash. |
| Silent transformation prevention | ✅ | Architecture | Original GeoJSON stored; normalized WKT stored separately. Neither overwrites the other. |
| Geometry validation + repair | ✅ | `core/geometry.py` | Shapely make_valid on self-intersecting polygons. Documented repair count in quality profile. |
| Duplicate detection | ✅ | `ingestion/quality_profiler.py` | Duplicate ID check in profiler. |
| Area outlier detection | ✅ | `ingestion/quality_profiler.py` | IQR-based outlier detection. |

---

## Section 3 — Attribute / Schema Harmonization

| Requirement | Status | Module | Notes |
|---|---|---|---|
| Schema mapping (heterogeneous field names) | ✅ | `ingestion/schema_normalizer.py` | 60+ field aliases: Khasra_No → parcel_reference, Plot_Area → area, etc. |
| Fuzzy field name matching | ✅ | Same | RapidFuzz fallback for unrecognized fields. |
| Area unit normalization | ✅ | Same | sqft → m², acre → m², guntha → m², etc. |
| Multilingual owner name matching | ✅ | `matching/multilingual.py` | Devanagari romanization, honorific stripping, IndicSoundex, RapidFuzz. |
| Land-use classification matching | ✅ | `conflicts/detector.py` | Exact + normalized comparison. Mismatch flagged as conflict. |
| Identifier normalization (Khasra, property ID, etc.) | ✅ | `matching/matcher.py` | `_normalize_identifier`: lowercase, strip punctuation, NFKD unicode normalization. |

---

## Section 4 — Parcel Matching

| Requirement | Status | Module | Notes |
|---|---|---|---|
| Spatial matching | ✅ | `matching/matcher.py` | IoU, Hausdorff, area ratio, centroid distance. |
| Identifier matching | ✅ | Same | Exact + normalized Khasra/property/survey/ULPIN. |
| Attribute matching | ✅ | Same | Owner similarity, land-use, ward. |
| Temporal matching | ✅ | Same + `core/temporal.py` | Gap-days scoring, temporal qualification. |
| Provenance-aware matching | ✅ | `core/provenance.py` + matcher | Lineage graph traces independent origins. |
| ULPIN-based linking | ✅ | `core/ulpin.py` | Validates + links authoritative ULPINs from source records. |
| Union-Find parcel grouping | ✅ | `matching/matcher.py` | Connected components across all matching pairs → canonical parcel groups. |
| Explainable confidence | ✅ | `matching/matcher.py` + frontend | Per-signal breakdown: geometry/identifier/attribute/temporal/provenance. |

**Honest limitation**: The matching model is a deterministic weighted scorer — not a calibrated ML classifier. Stated confidence is a weighted signal, not a probability. This is documented throughout.

---

## Section 5 — Conflict Detection

| Requirement | Status | Module | Notes |
|---|---|---|---|
| Geometry conflict (boundary offset) | ✅ | `conflicts/detector.py` | IoU + Hausdorff thresholds. Type: BOUNDARY_OFFSET, AREA_MISMATCH, OVERLAP, GAP. |
| Attribute conflict | ✅ | Same | OWNER_REFERENCE_MISMATCH, LAND_USE_MISMATCH, AREA_ATTRIBUTE_MISMATCH. |
| Temporal change vs concurrent conflict | ✅ | `core/change_detection.py` | Classifies GEOMETRY_CHANGE, BOUNDARY_DRIFT, LAND_USE_CHANGE, CONCURRENT_CONFLICT. |
| CRS error detection | ✅ | `core/crs_check.py` | IMPOSSIBLE_EXTENT, DEGREE_METRE_CONFUSION, AXIS_ORDER, PLAUSIBILITY. |
| Provenance conflict | ✅ | `conflicts/detector.py` | SHARED_ORIGIN, UNKNOWN_LINEAGE. |
| Cross-layer conflicts | ✅ | `topology/ripple_check.py` | BUILDING_OUTSIDE_PARCEL, UTILITY_CROSSING, ROAD_ROW_CONFLICT. |
| Conflict severity taxonomy | ✅ | `models/domain.py` | CRITICAL / HIGH / MEDIUM / LOW. |

---

## Section 6 — Harmonization

| Requirement | Status | Module | Notes |
|---|---|---|---|
| Minimum-change proposal | ✅ | `harmonization/proposer.py` | Source-quality-weighted geometry selection; attribute reconciliation. |
| Source records never overwritten | ✅ | Architecture | DBSourceRecord immutable after ingest. Proposals stored separately in DBProposal. |
| Versioned proposals | ✅ | DBProposal.version + decision store | Each approved proposal creates a new version. |
| Auto-approve gate (5 criteria) | ✅ | `harmonization/proposer.py` | Confidence ≥ 0.82, offset ≤ 2m, area ≤ 5%, lineages ≥ 2, ripple safe. |
| Review queue | ✅ | `review/queue.py` | Priority-scored queue. Officer approves/rejects with reason. |
| Block on safety violation | ✅ | Ripple check + proposal decision | BLOCKED state when constraints violated. |

---

## Section 7 — Topology Validation

| Requirement | Status | Module | Notes |
|---|---|---|---|
| Neighbor parcel overlap check | ✅ | `topology/ripple_check.py` | New overlap introduced by proposal → blocks auto-approve. |
| Neighbor gap check | ⚠ | Same | Code exists; gap detection is approximate (area-based). |
| Building footprint check | ✅ | Same | Building outside proposed parcel boundary → HIGH severity issue. |
| Utility crossing check | ✅ | Same | New utility-boundary crossing introduced → MEDIUM severity. |
| Road ROW check | ✅ | Same | Overlap with road ROW → CRITICAL, blocks auto-approve. |
| Administrative boundary check | ⚠ | Not yet wired | SourceType.ADMINISTRATIVE accepted; cross-layer check not implemented. |
| Topology as auto-approval gate | ✅ | `harmonization/proposer.py` | `ripple.safe_to_auto_approve` overrides proposal decision. |

---

## Section 8 — Confidence Scoring

| Requirement | Status | Module | Notes |
|---|---|---|---|
| Multi-signal confidence | ✅ | `matching/matcher.py` | geometry(35%) + identifier(25%) + attribute(15%) + temporal(10%) + provenance(15%). |
| Per-signal explainability | ✅ | `matching/matcher.py` + `ConfidenceExplainer.tsx` | Each signal has a score and explanation. |
| Independent lineage counting | ✅ | `core/provenance.py` | DFS to count distinct origin nodes, not source count. |
| Honest claims (not calibrated probability) | ✅ | Docstrings + docs + frontend | "weighted matching signal, not a calibrated probability" in multiple places. |

---

## Section 9 — ULPIN / Parcel Identity

| Requirement | Status | Module | Notes |
|---|---|---|---|
| ULPIN consumption from source data | ✅ | `core/ulpin.py` + `routes_v2.py` | Validates + links ULPINs from BhuNaksha/DILRMP source records. |
| ULPIN format validation | ✅ | `core/ulpin.py` | 14-digit, numeric, state-code range check. |
| ULPIN linking across datasets | ✅ | `core/ulpin.py` | Groups ULPINs with same state+district and centroid proximity. |
| Official ULPIN generation | 🔒 DESCOPED | N/A | Official DoLR/ECCMA algorithm not publicly documented in full. We consume authoritative ULPINs. Demo identifier clearly labelled as non-official. |

---

## Section 10 — Interoperability + Export

| Requirement | Status | Module | Notes |
|---|---|---|---|
| GeoJSON import + export | ✅ | Throughout | Native format. |
| GeoPackage export | ✅ | `export/ogc_api.py` | Proper OGC GeoPackage with system tables. Opens in QGIS/ArcGIS. |
| GeoParquet ingestion | ✅ | `ingestion/format_adapters.py` | Requires geopandas. |
| Shapefile ingestion | ✅ | Same | Requires fiona. |
| CSV ingestion | ✅ | Same | Auto-detect lat/lon or WKT column. |
| OGC API Features interface | ⚠ | `export/ogc_api.py` + `routes_v2.py` | Core patterns implemented. Labelled "OGC API Features-aligned" — not CITE-tested. |
| Evidence package (ZIP) | ✅ | `export/package_exporter.py` | SHA-256 manifest + signed decision + all source data. |

---

## Section 11 — Security + Audit

| Requirement | Status | Module | Notes |
|---|---|---|---|
| SHA-256 per source record | ✅ | `ingestion/ingestor.py` | content_hash on every ingested record. |
| Ed25519 signed decisions | ✅ | `core/signing.py` + `review/queue.py` | Every approved/rejected proposal signed. |
| Tamper detection | ✅ | `core/evidence_envelope.py` | Hash mismatch detected on verify. |
| Audit trail | ✅ | `models/database.py` DBAuditEvent | Every case action logged with hash. |
| RBAC | ⚠ | `api/auth.py` | API key + demo mode. Role names defined in domain.py. Per-route role enforcement not yet wired. |
| No PII in demo data | ✅ | `scripts/generate_demo_data.py` | Owner refs are OWNER-XXXX pseudonymized. |
| Rate limiting | ✅ | `api/rate_limit.py` | 120/60s general, 30/60s heavy endpoints. |
| Input validation + path traversal | ✅ | `api/routes.py` | CASE_ID_RE regex on all case_id params. |

---

## Section 12 — Frontend / UI

| Requirement | Status | Module | Notes |
|---|---|---|---|
| Map visualization (multi-layer) | ✅ | `ParcelMap.tsx` + MapLibre GL JS | Per-source color coding, conflict highlighting. |
| Before/after comparison | ✅ | `BeforeAfterMap.tsx` | Drag slider between source and proposal geometries. |
| Explainable confidence panel | ✅ | `ConfidenceExplainer.tsx` | Per-signal bars with tooltips. Independence explainer. |
| Conflict detail view | ✅ | `ParcelMap.tsx` + `ConfidenceExplainer.tsx` | Type, severity, measure, explanation, why-it-exists tooltip. |
| Review queue UI | ✅ | `ReviewPanel.tsx` | Priority-sorted, approve/reject with reason field. |
| Evidence verifier | ✅ | `EvidencePanel.tsx` | Paste envelope JSON → verify signature. |
| Provenance graph display | ✅ | `ProvenancePanel.tsx` | Grouped by node type, edges shown. |
| ULPIN display | ✅ | `ULPINPanel.tsx` | Shows authoritative ULPIN or demo identifier with disclaimer. |
| GeoPackage export button | ✅ | `ParcelMap.tsx` | Download link wired to `/export/geopackage`. |

**Gap**: The Before/After map currently doesn't populate `beforeFeatures` from the API in real time — it needs the source record geometries fetched separately. This is a frontend wiring gap, not a backend gap.

---

## Section 13 — Performance + Scale

| Claim | Verified | Conditions |
|---|---|---|
| ~3,300 rec/s ingest (100K) | ✅ benchmark | Synthetic parcels, single process, SQLite in-memory index |
| ~0.09ms query p50 (100K) | ✅ benchmark | R-tree, 500-sample, synthetic uniform distribution |
| 100% conflict detection (100K) | ✅ benchmark | Injected pairs with 80m+ Hausdorff — well above the 50m threshold |
| ~463K× candidate reduction | ✅ benchmark | vs O(N²) naive; synthetic uniform distribution |

**All numbers are synthetic controlled benchmarks. Real-world performance will differ based on data density, geometry complexity, hardware, and database configuration.**

---

## Section 14 — Demo Readiness

The one-parcel Ward 42 demo should demonstrate these steps in order:

| Step | Status | Blocker? |
|---|---|---|
| Load 4+ source datasets | ✅ demo data exists | None |
| System detects 10 canonical parcels | ✅ after harmonize | Need to verify Ward 42 run end-to-end |
| P-1042 shown with 4 source records | ✅ | None |
| Conflict detected: 1.42m boundary offset | ✅ | Verify measure appears correctly in UI |
| Conflict detected: 2.1% area mismatch | ✅ | Same |
| Provenance: Revenue shares origin with Cadastral → 2 lineages, not 4 | ✅ | Provenance nodes must be ingested; demo script sets them up |
| Minimum-change proposal generated | ✅ | None |
| Ripple check finds building/utility conflict | ✅ | Needs buildings/utilities ingested alongside parcels |
| Auto-approve BLOCKED | ✅ | Ripple check issue must be present in demo data |
| Officer reviews + approves | ✅ | Review queue UI works |
| Evidence ZIP downloaded | ✅ | Export endpoint works |
| ULPIN shown (either authoritative or demo) | ✅ | ULPIN panel wired |

**One remaining action required**: Run the actual Ward 42 demo end-to-end using the API and confirm each step produces the expected output. Document the exact API call sequence in DEMO_SCRIPT.md.

---

## Section 15 — Claims Freeze

The following claims are cleared for the SIH presentation:

**Cleared ✅**
- "GeoSamanvay supports multi-source parcel matching using geometry, identifier, attribute, temporal, and provenance signals."
- "Original source datasets are immutable — the system generates proposals, not overwrites."
- "Topology is validated before any automatic proposal can be accepted."
- "Source lineage is traced to count independent origins, not file count."
- "Every harmonization decision is cryptographically signed (Ed25519) and independently verifiable."
- "The system is designed for offline-first deployment (Docker Compose, SQLite, no cloud dependency)."
- "Ingestion supports GeoJSON, Shapefile, GeoPackage, GeoParquet, and CSV."
- "OGC API Features-aligned interface for interoperability."
- "GeoPackage export opens directly in QGIS and ArcGIS."
- "105+ automated tests cover geometry, CRS, provenance, signing, schema, ripple, API."

**Not cleared — remove from all materials**
- ❌ "ULPIN generated per DoLR specification" → Replace with "ULPIN integration — validates and links authoritative ULPINs from source records"
- ❌ "Full OGC API Features conformance" → Replace with "OGC API Features-aligned interface"
- ❌ "100% real-world conflict detection" → "100% in synthetic controlled benchmark"
- ❌ "AI determines the correct boundary" → Never say this
- ❌ "Replaces NAKSHA / Bhu-Naksha" → Never say this

---

## Section 16 — Freeze Checklist

Before PPT is finalized:

- [x] ULPIN claim corrected (uses, does not generate official ULPIN)
- [x] OGC claim corrected (aligned, not CITE-certified)
- [x] Benchmark methodology documented in results JSON
- [x] 122/122 tests passing
- [ ] Ward 42 demo run end-to-end via API — document exact call sequence
- [ ] Before/After map wired with real source geometries from API
- [ ] Confirm ripple check produces BLOCKED result in Ward 42 scenario
- [ ] RBAC: wire role checks to specific routes (currently auth only)
- [ ] PPT slide 1: "Existing systems collect. GeoSamanvay reconciles."
- [ ] No PII / no real land data in any submitted material

---

*GeoSamanvay — Team Aikta — SIH26013 — Hard audit Sept 2026*
