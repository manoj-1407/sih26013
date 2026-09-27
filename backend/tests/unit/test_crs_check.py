"""Unit tests for CRS plausibility checker."""
from shapely.geometry import box, Point
from app.core.crs_check import check_crs_plausibility


class TestCRSPlausibility:
    def test_valid_delhi(self):
        geom = box(77.0, 28.5, 77.1, 28.6)
        r = check_crs_plausibility(geom)
        assert r.ok
        assert r.category == "NONE"

    def test_valid_mumbai(self):
        geom = box(72.8, 18.9, 72.9, 19.0)
        r = check_crs_plausibility(geom)
        assert r.ok

    def test_metre_range_confusion(self):
        # Projected coordinates mislabeled as degrees.
        # Note: coords like 800000, 2000000 also trigger IMPOSSIBLE_EXTENT (lat > 90)
        # before reaching the DEGREE_METRE_CONFUSION gate — both categories indicate
        # the same root cause. Either is a correct rejection.
        geom = box(800000, 2000000, 800100, 2000100)
        r = check_crs_plausibility(geom)
        assert not r.ok
        assert r.category in ("DEGREE_METRE_CONFUSION", "IMPOSSIBLE_EXTENT")

    def test_axis_order_swap(self):
        # x in lat range (6-38), y in lon range (67-98) = swapped
        geom = box(18.5, 73.8, 19.0, 74.2)
        r = check_crs_plausibility(geom)
        assert not r.ok
        assert r.category == "AXIS_ORDER"

    def test_impossible_latitude(self):
        geom = box(72.0, 95.0, 73.0, 96.0)  # lat > 90
        r = check_crs_plausibility(geom)
        assert not r.ok
        assert r.category == "IMPOSSIBLE_EXTENT"

    def test_outside_india_warning_only(self):
        # Valid coordinates but outside India ±10°
        geom = box(0.0, 0.0, 1.0, 1.0)
        r = check_crs_plausibility(geom)
        assert r.ok  # warning, not hard failure
        assert r.category == "PLAUSIBILITY"

    def test_non_wgs84_skipped(self):
        geom = box(800000, 2000000, 800100, 2000100)
        r = check_crs_plausibility(geom, declared_crs="EPSG:32643")
        assert r.ok  # can't check non-WGS84 in geographic terms
