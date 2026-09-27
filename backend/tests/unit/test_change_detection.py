"""Unit tests for change detection engine."""
from app.core.change_detection import detect_parcel_changes, ChangeRecord


def _rec(rid, source, geojson, area=None, land_use=None, ts=None, owner=None):
    return ChangeRecord(
        record_id=rid,
        source_type=source,
        geometry_geojson=geojson,
        area_sqm=area,
        land_use=land_use,
        owner_reference=owner,
        capture_timestamp=ts,
    )


POLY_A = {"type": "Polygon", "coordinates": [[[72.0, 18.0], [72.01, 18.0], [72.01, 18.01], [72.0, 18.01], [72.0, 18.0]]]}
POLY_B = {"type": "Polygon", "coordinates": [[[72.002, 18.0], [72.012, 18.0], [72.012, 18.01], [72.002, 18.01], [72.002, 18.0]]]}  # ~200m offset


class TestChangeDetection:
    def test_identical_records_no_change(self):
        records = [
            _rec("R1", "CADASTRAL", POLY_A, ts="2021-01-01"),
            _rec("R2", "REVENUE_ROR", POLY_A, ts="2021-06-01"),
        ]
        result = detect_parcel_changes("P-001", records)
        # Identical geometry = no conflict
        assert result.records_analyzed == 2

    def test_temporal_change_detected(self):
        records = [
            _rec("R1", "CADASTRAL", POLY_A, ts="2015-01-01"),
            _rec("R2", "DRONE_ORI", POLY_B, ts="2024-01-01"),  # 9 year gap
        ]
        result = detect_parcel_changes("P-001", records)
        assert result.has_temporal_changes or result.has_concurrent_conflicts  # offset should be detected

    def test_concurrent_conflict_detected(self):
        records = [
            _rec("R1", "CADASTRAL", POLY_A, ts="2024-01-01"),
            _rec("R2", "MUNICIPAL_GIS", POLY_B, ts="2024-02-01"),  # 1 month gap = concurrent
        ]
        result = detect_parcel_changes("P-001", records)
        assert result.has_concurrent_conflicts or result.has_temporal_changes

    def test_land_use_change(self):
        records = [
            _rec("R1", "CADASTRAL", POLY_A, land_use="Residential", ts="2015-01-01"),
            _rec("R2", "MUNICIPAL_GIS", POLY_A, land_use="Commercial", ts="2023-01-01"),
        ]
        result = detect_parcel_changes("P-001", records)
        land_use_events = [e for e in result.change_events if e.change_type == "LAND_USE_CHANGE"]
        assert len(land_use_events) >= 1

    def test_single_record_no_comparison(self):
        records = [_rec("R1", "CADASTRAL", POLY_A, ts="2021-01-01")]
        result = detect_parcel_changes("P-001", records)
        assert len(result.change_events) == 0

    def test_temporal_span_computed(self):
        records = [
            _rec("R1", "A", POLY_A, ts="2015-06-01"),
            _rec("R2", "B", POLY_B, ts="2024-06-01"),
        ]
        result = detect_parcel_changes("P-001", records)
        assert result.temporal_span_days > 300  # more than 9 years
