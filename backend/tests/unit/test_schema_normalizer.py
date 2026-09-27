"""Unit tests for schema normalizer."""
from app.ingestion.schema_normalizer import normalize_attributes


class TestSchemaMapping:
    def test_cadastral_fields(self):
        attrs = {"Khasra_No": "1042", "Owner_Name": "Ramesh Kumar", "Area": 1245, "Land_Use": "Residential"}
        r = normalize_attributes(attrs)
        assert r.canonical["parcel_reference"] == "1042"
        assert r.canonical["owner_reference"] == "Ramesh Kumar"
        assert r.canonical["area"] == 1245
        assert r.canonical["land_use"] == "Residential"

    def test_municipal_fields(self):
        attrs = {"Property_ID": "MUN-W42-1042", "Owner": "R. Kumar", "Plot_Area": 1219, "Usage_Type": "Residential"}
        r = normalize_attributes(attrs)
        assert r.canonical["parcel_reference"] == "MUN-W42-1042"
        assert r.canonical["owner_reference"] == "R. Kumar"
        assert r.canonical["area"] == 1219

    def test_drone_fields(self):
        attrs = {"Parcel_ID": "DRN-1042", "Measured_Area": 1231, "Use": "Residential"}
        r = normalize_attributes(attrs)
        assert r.canonical["parcel_reference"] == "DRN-1042"
        assert r.canonical["area"] == 1231

    def test_area_sqft_conversion(self):
        attrs = {"area": 13400, "unit": "sqft"}
        r = normalize_attributes(attrs)
        # 13400 sqft * 0.0929 = 1244.86 m²
        assert r.area_sqm is not None
        assert abs(r.area_sqm - 1244.86) < 1.0

    def test_unmapped_field_preserved(self):
        attrs = {"totally_unknown_field": "value", "Khasra_No": "1042"}
        r = normalize_attributes(attrs)
        assert "totally_unknown_field" in r.unmapped
        assert r.canonical["parcel_reference"] == "1042"

    def test_ulpin(self):
        attrs = {"ULPIN": "12345678901234", "bhu_aadhaar": "98765432109876"}
        r = normalize_attributes(attrs)
        assert r.canonical.get("ulpin") is not None

    def test_empty_attributes(self):
        r = normalize_attributes({})
        assert r.canonical == {}
        assert r.unmapped == {}
