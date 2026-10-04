"""Unit tests for topology_correction.py and explain_confidence."""
import pytest
from shapely.geometry import box, mapping as sh_map
from shapely.affinity import translate


M2DEG = 1.0 / 111_000.0
BASE_LON, BASE_LAT = 73.85, 18.52
W = 35 * M2DEG
H = 42 * M2DEG


# ─────────────────────────────────────────────────────────────────────────────
# Topology correction
# ─────────────────────────────────────────────────────────────────────────────

class TestOverlapCorrection:
    def test_overlap_detected_and_corrected(self):
        from app.core.topology_correction import correct_overlap
        pa = box(BASE_LON, BASE_LAT, BASE_LON + W, BASE_LAT + H)
        pb = box(BASE_LON, BASE_LAT, BASE_LON + W * 1.15, BASE_LAT + H)
        result = correct_overlap("A", "B", dict(sh_map(pa)), dict(sh_map(pb)),
                                 quality_weight_a=0.80, quality_weight_b=0.70)
        assert result is not None
        assert result.correction_type == "OVERLAP_SPLIT"
        # Higher-weight source (A) should keep its original boundary
        assert result.area_a_after_sqm == pytest.approx(result.area_a_before_sqm, rel=0.02)
        # Lower-weight source (B) should lose overlap area
        assert result.area_b_after_sqm < result.area_b_before_sqm
        assert result.overlap_area_removed_sqm > 0

    def test_no_overlap_returns_none(self):
        from app.core.topology_correction import correct_overlap
        pa = box(BASE_LON, BASE_LAT, BASE_LON + W, BASE_LAT + H)
        # Disjoint parcel — far away
        pb = box(BASE_LON + W * 3, BASE_LAT, BASE_LON + W * 4, BASE_LAT + H)
        result = correct_overlap("A", "B", dict(sh_map(pa)), dict(sh_map(pb)))
        assert result is None

    def test_higher_quality_wins_overlap(self):
        from app.core.topology_correction import correct_overlap
        # Both parcels start at same origin; A is smaller (fits within B)
        # Use side-by-side overlap instead: B starts at 85% of A's width
        lon2 = BASE_LON + W * 0.85
        pa = box(BASE_LON, BASE_LAT, BASE_LON + W, BASE_LAT + H)
        pb = box(lon2, BASE_LAT, lon2 + W, BASE_LAT + H)
        # B has higher weight -- A should lose the overlap zone
        result = correct_overlap("A", "B", dict(sh_map(pa)), dict(sh_map(pb)),
                                 quality_weight_a=0.70, quality_weight_b=0.90)
        assert result is not None
        # A (lower weight) loses area to B
        assert result.area_a_after_sqm < result.area_a_before_sqm

    def test_correction_has_required_fields(self):
        from app.core.topology_correction import correct_overlap
        pa = box(BASE_LON, BASE_LAT, BASE_LON + W, BASE_LAT + H)
        pb = box(BASE_LON, BASE_LAT, BASE_LON + W * 1.12, BASE_LAT + H)
        r = correct_overlap("A", "B", dict(sh_map(pa)), dict(sh_map(pb)))
        assert r is not None
        assert r.correction_id.startswith("TOPO-")
        assert r.geometry_a_before is not None
        assert r.geometry_a_after is not None
        assert r.geometry_b_before is not None
        assert r.geometry_b_after is not None
        assert len(r.caveats) > 0
        assert r.description != ""


class TestGapCorrection:
    def test_gap_detected_and_filled(self):
        from app.core.topology_correction import correct_gap
        pa = box(BASE_LON, BASE_LAT, BASE_LON + W, BASE_LAT + H)
        # Place B clearly separate from A — 3×W gap between them
        pb = box(BASE_LON + W * 4, BASE_LAT, BASE_LON + W * 5, BASE_LAT + H)
        result = correct_gap("A", "B", dict(sh_map(pa)), dict(sh_map(pb)))
        assert result is not None
        assert result.correction_type in ("GAP_FILL", "GAP_LARGE")
        assert result.gap_area_filled_sqm >= 0

    def test_large_gap_flagged_not_auto_corrected(self):
        from app.core.topology_correction import correct_gap
        pa = box(BASE_LON, BASE_LAT, BASE_LON + W, BASE_LAT + H)
        # Very large gap — 10×W away
        pb = box(BASE_LON + W * 11, BASE_LAT, BASE_LON + W * 12, BASE_LAT + H)
        result = correct_gap("A", "B", dict(sh_map(pa)), dict(sh_map(pb)))
        assert result is not None
        assert result.correction_type == "GAP_LARGE"
        assert result.correction_confidence == 0.0

    def test_no_gap_returns_none(self):
        from app.core.topology_correction import correct_gap
        pa = box(BASE_LON, BASE_LAT, BASE_LON + W, BASE_LAT + H)
        # Exact same geometry
        pb = box(BASE_LON, BASE_LAT, BASE_LON + W, BASE_LAT + H)
        result = correct_gap("A", "B", dict(sh_map(pa)), dict(sh_map(pb)))
        assert result is None


class TestBoundaryOffsetCorrection:
    def test_small_offset_corrected(self):
        from app.core.topology_correction import correct_boundary_offset
        pa = box(BASE_LON, BASE_LAT, BASE_LON + W, BASE_LAT + H)
        pb = translate(pa, 3 * M2DEG, 1 * M2DEG)
        result = correct_boundary_offset("A", "B", dict(sh_map(pa)), dict(sh_map(pb)),
                                         quality_weight_a=0.80, quality_weight_b=0.90,
                                         max_correction_m=5.0)
        assert result is not None
        assert result.correction_type == "BOUNDARY_ALIGN"
        assert result.boundary_shift_m > 0
        assert result.correction_confidence > 0

    def test_large_offset_flagged(self):
        from app.core.topology_correction import correct_boundary_offset
        pa = box(BASE_LON, BASE_LAT, BASE_LON + W, BASE_LAT + H)
        pb = translate(pa, 20 * M2DEG, 0)
        result = correct_boundary_offset("A", "B", dict(sh_map(pa)), dict(sh_map(pb)),
                                         max_correction_m=5.0)
        assert result is not None
        assert result.correction_type == "OFFSET_TOO_LARGE"
        assert result.correction_confidence == 0.0

    def test_sub_noise_offset_returns_none(self):
        from app.core.topology_correction import correct_boundary_offset
        pa = box(BASE_LON, BASE_LAT, BASE_LON + W, BASE_LAT + H)
        pb = translate(pa, 0.2 * M2DEG, 0)
        result = correct_boundary_offset("A", "B", dict(sh_map(pa)), dict(sh_map(pb)))
        assert result is None


class TestAutoCorrect:
    def test_dispatch_overlap(self):
        from app.core.topology_correction import auto_correct
        pa = box(BASE_LON, BASE_LAT, BASE_LON + W, BASE_LAT + H)
        pb = box(BASE_LON, BASE_LAT, BASE_LON + W * 1.12, BASE_LAT + H)
        r = auto_correct("A", "B", dict(sh_map(pa)), dict(sh_map(pb)), "OVERLAP")
        assert r is not None
        assert r.correction_type == "OVERLAP_SPLIT"

    def test_dispatch_gap(self):
        from app.core.topology_correction import auto_correct
        pa = box(BASE_LON, BASE_LAT, BASE_LON + W, BASE_LAT + H)
        # Clearly separate parcel — 4×W gap
        pb = box(BASE_LON + W * 5, BASE_LAT, BASE_LON + W * 6, BASE_LAT + H)
        r = auto_correct("A", "B", dict(sh_map(pa)), dict(sh_map(pb)), "GAP")
        assert r is not None

    def test_dispatch_boundary_offset(self):
        from app.core.topology_correction import auto_correct
        pa = box(BASE_LON, BASE_LAT, BASE_LON + W, BASE_LAT + H)
        pb = translate(pa, 3 * M2DEG, 1 * M2DEG)
        r = auto_correct("A", "B", dict(sh_map(pa)), dict(sh_map(pb)),
                         "BOUNDARY_OFFSET", quality_weight_a=0.80, quality_weight_b=0.90)
        assert r is not None

    def test_unknown_conflict_type_returns_none(self):
        from app.core.topology_correction import auto_correct
        pa = box(BASE_LON, BASE_LAT, BASE_LON + W, BASE_LAT + H)
        pb = box(BASE_LON, BASE_LAT, BASE_LON + W, BASE_LAT + H)
        r = auto_correct("A", "B", dict(sh_map(pa)), dict(sh_map(pb)), "OWNER_MISMATCH")
        assert r is None


# ─────────────────────────────────────────────────────────────────────────────
# Confidence explainer
# ─────────────────────────────────────────────────────────────────────────────

class TestExplainConfidence:
    def _make_ev(self, geo=0.9, idf=1.0, attr=0.85, temp=0.80, prov=0.80,
                 iou=0.92, hd=1.5, owner=0.90, lineages=2):
        from app.matching.matcher import MatchEvidence, WEIGHTS
        overall = (geo * WEIGHTS["geometry"] + idf * WEIGHTS["identifier"]
                   + attr * WEIGHTS["attributes"] + temp * WEIGHTS["temporal"]
                   + prov * WEIGHTS["provenance"])
        return MatchEvidence(
            geometry_score=geo, identifier_score=idf, attribute_score=attr,
            temporal_score=temp, provenance_score=prov, overall_score=round(overall, 4),
            iou=iou, hausdorff_m=hd, area_ratio_diff=0.02, centroid_dist_m=1.2,
            identifier_match_type="exact", matched_identifier="1042",
            owner_similarity=owner, land_use_match=True,
            temporal_gap_days=180, independent_lineages=lineages, explanation=[],
        )

    def test_returns_five_signals(self):
        from app.matching.matcher import explain_confidence
        ev = self._make_ev()
        result = explain_confidence(ev)
        assert len(result["signals"]) == 5
        signal_names = {s["signal"] for s in result["signals"]}
        assert signal_names == {"geometry", "identifier", "attributes", "temporal", "provenance"}

    def test_contributions_sum_to_overall(self):
        from app.matching.matcher import explain_confidence
        ev = self._make_ev()
        result = explain_confidence(ev)
        total = sum(s["contribution"] for s in result["signals"])
        assert total == pytest.approx(ev.overall_score, abs=0.001)

    def test_high_confidence_verdict(self):
        from app.matching.matcher import explain_confidence, HIGH_CONF_THRESHOLD
        ev = self._make_ev(geo=0.97, idf=1.0, attr=0.95, temp=0.90, prov=0.90)
        result = explain_confidence(ev)
        assert result["overall_score"] >= HIGH_CONF_THRESHOLD
        assert result["verdict"] == "HIGH_CONFIDENCE"

    def test_review_required_verdict(self):
        from app.matching.matcher import explain_confidence, REVIEW_THRESHOLD, HIGH_CONF_THRESHOLD
        # Scores chosen to land between 0.75 and 0.88
        ev = self._make_ev(geo=0.80, idf=0.90, attr=0.80, temp=0.85, prov=0.60)
        result = explain_confidence(ev)
        assert REVIEW_THRESHOLD <= result["overall_score"] < HIGH_CONF_THRESHOLD, \
            f"Expected score in [{REVIEW_THRESHOLD}, {HIGH_CONF_THRESHOLD}), got {result['overall_score']}"
        assert result["verdict"] == "REVIEW_REQUIRED"

    def test_low_confidence_verdict(self):
        from app.matching.matcher import explain_confidence, MATCH_THRESHOLD, REVIEW_THRESHOLD
        ev = self._make_ev(geo=0.70, idf=0.0, attr=0.20, temp=0.30, prov=0.30)
        result = explain_confidence(ev)
        assert result["overall_score"] < REVIEW_THRESHOLD
        assert result["verdict"] in ("LOW_CONFIDENCE", "NO_MATCH")

    def test_provenance_penalty_visible(self):
        from app.matching.matcher import explain_confidence
        ev = self._make_ev(prov=0.30, lineages=1)
        result = explain_confidence(ev)
        prov_signal = next(s for s in result["signals"] if s["signal"] == "provenance")
        assert prov_signal["delta"] < 0, "Shared origin should produce negative delta"
        assert "shared" in prov_signal["narrative"].lower() or "correlated" in prov_signal["narrative"].lower()

    def test_narrative_present(self):
        from app.matching.matcher import explain_confidence
        ev = self._make_ev()
        result = explain_confidence(ev)
        assert len(result["narrative"]) > 20
        assert result["recommendation"] != ""

    def test_delta_signs_correct(self):
        from app.matching.matcher import explain_confidence
        ev_high = self._make_ev(geo=0.95)
        ev_low  = self._make_ev(geo=0.10)
        res_high = explain_confidence(ev_high)
        res_low  = explain_confidence(ev_low)
        geo_high = next(s for s in res_high["signals"] if s["signal"] == "geometry")
        geo_low  = next(s for s in res_low["signals"]  if s["signal"] == "geometry")
        assert geo_high["delta"] > 0,  "High geometry score should have positive delta"
        assert geo_low["delta"]  < 0,  "Low geometry score should have negative delta"
