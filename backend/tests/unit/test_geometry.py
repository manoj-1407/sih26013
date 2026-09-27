"""Unit tests for geometry engine."""
import pytest
from shapely.geometry import box, Point

from app.core.geometry import (
    validate_geojson_geometry, normalize_to_wgs84, compute_iou,
    compute_hausdorff_metres, compare_geometries, area_sqm,
)


class TestValidation:
    def test_valid_polygon(self):
        geom = {"type": "Polygon", "coordinates": [[[72, 18], [73, 18], [73, 19], [72, 19], [72, 18]]]}
        r = validate_geojson_geometry(geom)
        assert r.valid

    def test_missing_type(self):
        r = validate_geojson_geometry({"coordinates": [[[1,2],[3,4],[1,2]]]})
        assert not r.valid

    def test_empty_geometry(self):
        r = validate_geojson_geometry({"type": "Polygon", "coordinates": []})
        assert not r.valid

    def test_non_dict(self):
        r = validate_geojson_geometry("not a dict")
        assert not r.valid

    def test_self_intersecting_repaired(self):
        # Bowtie polygon — self-intersecting, should be repaired
        geom = {"type": "Polygon", "coordinates": [[[0,0],[1,1],[0,1],[1,0],[0,0]]]}
        r = validate_geojson_geometry(geom)
        assert r.valid  # make_valid repairs it

    def test_geometry_collection_empty(self):
        r = validate_geojson_geometry({"type": "GeometryCollection", "geometries": []})
        assert not r.valid


class TestIoU:
    def test_identical(self):
        g = box(0, 0, 1, 1)
        assert compute_iou(g, g) == pytest.approx(1.0)

    def test_disjoint(self):
        a = box(0, 0, 1, 1)
        b = box(5, 5, 6, 6)
        assert compute_iou(a, b) == pytest.approx(0.0)

    def test_half_overlap(self):
        a = box(0, 0, 2, 1)
        b = box(1, 0, 3, 1)
        # intersection = 1x1, union = 3x1 = 3 → IoU = 1/3
        assert compute_iou(a, b) == pytest.approx(1/3, rel=1e-3)

    def test_non_polygon_returns_minus_one(self):
        a = Point(0, 0)
        b = Point(1, 1)
        assert compute_iou(a, b) == -1.0


class TestHausdorff:
    def test_identical_zero(self):
        g = box(0, 0, 0.01, 0.01)
        hd = compute_hausdorff_metres(g, g)
        assert hd == pytest.approx(0.0)

    def test_offset_positive(self):
        a = box(78.0, 18.0, 78.001, 18.001)
        b = box(78.001, 18.0, 78.002, 18.001)
        hd = compute_hausdorff_metres(a, b)
        assert hd > 0


class TestCompareGeometries:
    def test_identical_no_conflict(self):
        g = box(72.0, 18.0, 72.001, 18.001)
        r = compare_geometries(g, g)
        assert not r.conflict

    def test_large_offset_conflict(self):
        a = box(72.0, 18.0, 72.01, 18.01)
        b = box(72.02, 18.0, 72.03, 18.01)
        r = compare_geometries(a, b)
        assert r.conflict

    def test_measurements_populated(self):
        a = box(72.0, 18.0, 72.01, 18.01)
        b = box(72.005, 18.0, 72.015, 18.01)
        r = compare_geometries(a, b)
        assert "iou" in r.measurements
        assert "hausdorff_m" in r.measurements
        assert "area_ratio_diff" in r.measurements
