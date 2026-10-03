# GeoSamanvay — Competition Q&A Bank
## SIH26013 · Team Aikta · 30-second answers

Each answer is written to be delivered in ≤ 30 seconds verbally.
Where the answer has a code/data basis, the source file is noted.

---

## SECTION 1 — Problem understanding

### Q1. Why aren't existing GIS tools enough?
Tools like QGIS and ArcGIS are excellent for viewing and editing spatial data. They don't answer the question that land governance actually needs answered: *which of these four conflicting records should I trust, and what happens to the neighbourhood if I act on it?* GeoSamanvay is not a GIS editor — it's a reconciliation layer that sits between raw source data and the authoritative record, and it's the only one that traces whether those sources are genuinely independent.

### Q2. Why does this problem require a purpose-built system?
Because three things have to happen simultaneously that no existing tool combines: (a) prove that sources are independent, not just different files; (b) evaluate downstream spatial consequences before approving a boundary change; (c) produce a cryptographically auditable decision that can be verified years later without server access. None of the existing cadastral, revenue, or GIS platforms do all three.

### Q3. Why not simply trust the government-authoritative source?
Because the PS explicitly exists because there is *no single agreed authoritative source*. Cadastral, revenue, municipal GIS, and drone ORI frequently conflict. The Ministry's own problem statement says the goal is intelligent harmonisation, not "pick one." GeoSamanvay proposes the minimum defensible change and requires an authorised human to approve it — it never silently picks a winner.

---

## SECTION 2 — Technical

### Q4. How does parcel matching actually work?
Five weighted signals: geometry similarity (IoU + Hausdorff + area ratio + centroid distance, 35%), identifier overlap (Khasra/ULPIN/property ID exact/normalised/partial, 25%), attribute similarity (owner name fuzzy match + land-use + ward, 15%), temporal score (capture date gap, 10%), and provenance independence (DAG lineage count, 15%). An R-tree spatial index pre-filters candidates before scoring. Source: `backend/app/matching/matcher.py`.

### Q5. How do you handle coordinate reference system differences?
Four gates run on every record at ingest time: (1) pre-ingest coordinate range check — values > 1,000 indicate projected metres, not degrees; (2) latitude bounds — |y| > 90 is impossible; (3) post-normalisation India bounding-box plausibility; (4) axis-order heuristic — if x ∈ [6,38] and y ∈ [68,97] for an Indian dataset, the lat/lon axes are likely swapped. Rejected records are logged with reason. Source: `backend/app/core/crs_check.py`.

### Q6. How do you handle conflicting sources?
Conflict detection runs pairwise across every matched source group. It classifies: BOUNDARY_OFFSET, AREA_MISMATCH, OVERLAP, GAP (geometry); OWNER_REFERENCE_MISMATCH, LAND_USE_MISMATCH, AREA_ATTRIBUTE_MISMATCH (attributes); SHARED_ORIGIN, UNKNOWN_LINEAGE (provenance); and ADMIN_BOUNDARY_CROSSING, BUILDING_OUTSIDE, UTILITY_CROSSING, ROW_CONFLICT (topology). Each conflict has a severity, a measure, and a natural-language description. Source: `backend/app/conflicts/detector.py`.

### Q7. What is provenance, technically?
A directed acyclic graph where nodes are origins, datasets, transformations, and records. Every source record has a provenance_node_id that traces back through parent edges to a root origin node. Independence analysis does a DFS from each record to count distinct root origins. Four files from one 1999 survey → one independent observation, not four. Source: `backend/app/core/provenance.py`.

### Q8. What is ripple validation, exactly?
Before any proposal can be auto-approved, the system checks the proposed new geometry against: neighbouring parcels (new overlap or gap introduced?), building footprints (building outside parcel boundary?), utility networks (new line crossing introduced?), road rights-of-way (ROW encroachment?), and administrative boundaries (ward/tehsil crossing?). Any blocking issue forces REVIEW_REQUIRED regardless of match confidence. Source: `backend/app/topology/ripple_check.py`.

### Q9. Why do you use confidence scoring?
So a judge can see *why* the system is confident or uncertain, not just that it is. The five-signal breakdown means an officer reviewing a proposal can immediately see: "geometry is 91%, identifier is 100%, but provenance is only 30% because both records share the same 1999 survey origin." That's an explanation, not a magic number.

### Q10. What exactly is the five-gate auto-approval model?
Gate 1: overall match confidence ≥ 0.82. Gate 2: boundary offset ≤ 2.0m. Gate 3: area change ≤ 5%. Gate 4: ≥ 2 independent source lineages. Gate 5: ripple check passes with no blocking issues. All five must pass. Any single failure forces REVIEW_REQUIRED. Critical issues force BLOCKED. Source: `backend/app/harmonization/proposer.py`.

---

## SECTION 3 — AI and ML

### Q11. Where is AI actually used in GeoSamanvay?
In two places. (1) An optional LightGBM reranker for spatial match scoring — it trains on an 11-feature vector (IoU, Hausdorff, identifier score, owner similarity, etc.) and blends its probability 60/40 with the deterministic score. (2) The multilingual name matching module uses RapidFuzz with Devanagari romanisation and IndicSoundex for cross-script owner name comparison. The deterministic gates cannot be overridden by ML in either case. Source: `backend/app/matching/ml_reranker.py`, `backend/app/matching/multilingual.py`.

### Q12. What happens if the AI is wrong?
Nothing bad, by design. The LightGBM score is blended with a deterministic score (not replacing it), and the result feeds the confidence signal. The five-gate auto-approval system uses hard geometric and topological constraints that the ML layer cannot override. A high ML score on a parcel with 9 blocking ripple issues still gets REVIEW_REQUIRED. Source: `backend/app/harmonization/proposer.py` lines 182–200.

### Q13. How is AI validated?
The LightGBM model is trained on a synthetic labelled corpus of 4,000 positive/negative parcel-match pairs and evaluated on a held-out 20% split. Precision, recall, and F1 are reported at training time. The model is explicitly labelled "synthetic training data only — not validated on real land records" in code and docs. In production, this model would be replaced with manually adjudicated pairs from real cadastral datasets.

---

## SECTION 4 — Security

### Q14. How is evidence protected?
Every harmonisation decision produces a signed evidence envelope: canonical JSON serialisation → SHA-256 hash stored in `evidence_hash` → Ed25519 private key signs the canonical bytes → stored in `signature`. Verification is stateless: reconstruct the payload, recompute the hash, check it matches, then verify the signature against the trust registry. No database access needed to verify. Source: `backend/app/core/evidence_envelope.py`.

### Q15. Can an administrator alter a recorded decision?
They can change the database row, but they cannot make the evidence envelope verify as valid after doing so. The envelope's hash is computed over the canonical payload at sign time. Any field change — including the decision itself — produces a different hash, which breaks both the hash check and the signature. The tamper demo shows this live: change `decision` from REVIEW_REQUIRED to AUTO_APPROVED → verification returns "evidence_hash mismatch — payload has been tampered with."

### Q16. How exactly does tamper detection work?
Canonical JSON (sorted keys, no whitespace) is serialised from the payload. SHA-256 is computed. Ed25519 signs the bytes. At verification: the envelope fields (excluding `evidence_hash`, `signature`, `signing`) are re-serialised identically. The hash is recomputed. If it differs from `evidence_hash`, the payload was tampered with before the signature check even runs. If the hash matches but the signature is invalid, the key was wrong or the signature was forged. Source: `backend/app/core/evidence_envelope.py` `verify_envelope()`.

### Q17. How does RBAC work?
Five roles: VIEWER, ANALYST, REVIEWER, APPROVER, ADMIN. In demo mode (GS_DEMO_MODE=1) all roles are granted for judging convenience. In production, the `X-GS-Role` header is validated. The proposal decide endpoint requires REVIEWER or APPROVER. An ANALYST attempting to approve gets HTTP 403. The `require_reviewer` FastAPI dependency handles this. Validated in the judge validation script — ANALYST returns 403, REVIEWER returns 200. Source: `backend/app/api/auth.py`.

---

## SECTION 5 — Scale and performance

### Q18. What happens at 1 million parcels?
The R-tree spatial index scales sub-linearly — at 100K parcels the p50 query time is ~0.09ms with ~463,000× candidate reduction vs naive O(N²) pairing. The harmonisation pipeline is stateless and horizontally scalable. At production scale, SQLite would be replaced with PostGIS (swap via DATABASE_URL env var, no code change needed). The bottleneck at national scale would be the database write throughput during bulk ingest, not the matching algorithm.

### Q19. What is the actual bottleneck?
At current single-process ingest: ~3,673 records/sec on synthetic parcels with SQLite. At 10 million parcels that means ~45 minutes for a district-scale ingest in a single worker. Production deployment would use parallel workers, async job queues, and PostGIS BRIN indexes. The system architecture separates the HTTP API from the processing pipeline for exactly this reason.

### Q20. How do you process large ORI imagery?
GeoSamanvay does not process raw rasters. It consumes the output of an upstream feature extraction tool (QGIS Semi-Automatic, SAM, YOLO-seg, etc.) as GeoJSON boundary candidates. The imagery adapter in `backend/app/ingestion/imagery_adapter.py` tags these as `DRONE_ORI` source type with the appropriate quality weight (0.92 for sub-5cm GSD) and a provenance node marking them as imagery-derived. This keeps boundary detection concerns separate from reconciliation concerns.

---

## SECTION 6 — Government and deployment

### Q21. How would a state department actually deploy this?
Three modes: (1) Docker Compose — `git clone && docker compose up` gives a working system in ~5 minutes, no external dependencies; (2) cloud deployment via Render using the committed `render.yaml`; (3) on-premise with a PostGIS database by setting `DATABASE_URL`. The system is designed to sit alongside — not replace — existing BhuNaksha/DILRMP/state RoR systems. It accepts their exports, reconciles them, and sends approved proposals back.

### Q22. What existing government systems does it integrate with?
Input: BhuNaksha GeoPackage exports, state RoR CSV/GeoJSON, Municipal GIS shapefiles, Survey of India GeoTIFF products. It reads ULPIN identifiers from authoritative sources (BhuNaksha, DILRMP) and uses them as a strong matching signal. Output: OGC GeoPackage (opens directly in QGIS/ArcGIS), GeoJSON, signed evidence ZIP. The OGC API Features-aligned interface allows any OGC-compliant client to query parcels and conflicts.

### Q23. Who approves the final record?
An authorised human officer with REVIEWER or APPROVER role. GeoSamanvay never writes a final approved record autonomously. Every auto-approved proposal still creates a signed evidence package that any auditor can verify. For proposals that fail the five gates, the system adds them to the review queue with a priority score based on conflict severity, match confidence, and ripple impact. The officer sees: what conflicts, why it was flagged, what the proposed change is, and what the downstream consequences would be.

---

## SECTION 7 — Competition

### Q24. How is GeoSamanvay different from A.L.I.G.N.?
A.L.I.G.N.'s philosophy is "fix the old map" — it warps, snaps, and rectifies legacy cadastral data. GeoSamanvay's philosophy is "don't overwrite anything." Every source record is immutable after ingest. A.L.I.G.N. has stronger imagery segmentation (FastSAM/SAM-2). GeoSamanvay has provenance-aware independence counting, ripple topology gating, and cryptographically verifiable decisions — none of which are visible in A.L.I.G.N.'s public repo or demo. These are exactly the properties a government land system needs before adopting any AI output.

### Q25. Why can't QGIS or ArcGIS solve this?
They can display and edit conflicting data. They cannot tell you that Cadastral and Revenue/RoR share the same 1999 survey origin and therefore agree for non-independent reasons. They cannot block a boundary edit because it would introduce a utility crossing two parcels away. They cannot produce a cryptographically verifiable, tamper-evident record of who approved what and on what evidence. These are reconciliation and governance capabilities, not cartography capabilities.

### Q26. Why should the ministry select GeoSamanvay over other teams?
Three things that are hard to fake: (1) the provenance independence DAG — verifiable in the API, live demo, and code; (2) the ripple topology gating — shows a specific parcel, specific issues, specific reasons for blocking, live; (3) the Ed25519 tamper demo — change one field, verification fails, live, no scripted demo. These aren't UI features. They're architectural properties that answer "can this system be trusted in a government land record workflow?"

---

## SECTION 8 — Limitations (answer these honestly and directly)

### Q27. What can't the system currently do?
Five honest limitations: (1) We don't process raw ORI/satellite rasters — we consume already-extracted feature vectors; (2) The LightGBM matching model is trained on synthetic data, not real adjudicated cadastral pairs; (3) OGC CITE conformance testing has not been performed — we say "aligned," not "certified"; (4) GNSS accuracy modelling is not implemented — coordinates are accepted at face value; (5) The evidence envelope uses a demo key; production deployment needs a proper PKI.

### Q28. What happens with bad source data?
Geometry validation rejects: self-intersecting polygons (make_valid attempted first), empty geometries, impossible coordinates, metre-range values mislabelled as degrees. Quality profiler flags: duplicate IDs, missing timestamps, area outliers (IQR), low geometry validity rate. Rejected records are logged with reason — not silently dropped. A quality report endpoint (`/cases/{id}/quality-report`) shows per-dataset acceptance rates, warnings, and a SHA-256 source manifest hash.

### Q29. What happens if there is no independent source?
The provenance score drops to 0.3 (shared-origin penalty). The match confidence falls below the 0.82 auto-approval gate. The proposal goes to REVIEW_REQUIRED. The review queue item shows "insufficient independent evidence" in its reason. The officer sees this explicitly. We don't pretend to have evidence we don't have — that's the entire point of the independence analysis.

### Q30. What's your biggest technical risk before the Grand Finale?
The LightGBM reranker requires `lightgbm` to be installed. On the current Render free tier it installs fine, but the cold-start time is ~3 minutes. For the demo we ensure the Ward42 case is pre-loaded so the judge doesn't wait. The fallback — pure deterministic scoring — works identically except the LightGBM blend doesn't activate. The health endpoint shows `ml_reranker: "deterministic_only"` in that case, which we treat as a feature (honest capability disclosure) not a failure.

---

*Last updated: October 2026 · GeoSamanvay SIH26013 · Team Aikta*
