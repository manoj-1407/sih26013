"""Unit tests for ULPIN validation + demo identifier generation."""
from app.core.ulpin import (
    validate_ulpin, normalize_ulpin, link_ulpins,
    extract_ulpin_from_attributes,
    generate_demo_identifier, demo_identifier_from_geometry,
)


class TestULPINValidation:
    """Tests for authoritative ULPIN format validation."""

    def test_valid_format(self):
        # Fabricated but format-correct 14-digit ULPIN
        r = validate_ulpin("15421852073856")
        assert r.valid
        assert r.state_code == "15"

    def test_wrong_length_short(self):
        r = validate_ulpin("12345")
        assert not r.valid
        assert "14 digits" in r.message

    def test_wrong_length_long(self):
        r = validate_ulpin("123456789012345")
        assert not r.valid

    def test_non_digit(self):
        r = validate_ulpin("1234567890123X")
        assert not r.valid
        assert "digits" in r.message

    def test_empty(self):
        r = validate_ulpin("")
        assert not r.valid

    def test_none_like(self):
        r = validate_ulpin("  ")
        assert not r.valid

    def test_with_spaces_normalized(self):
        r = validate_ulpin("15 42 185207 3856")
        assert r.valid  # spaces stripped during normalization

    def test_with_dashes_normalized(self):
        r = validate_ulpin("15-42-18520-73856")
        assert r.valid

    def test_invalid_state_code_00(self):
        r = validate_ulpin("00421852073856")
        assert not r.valid
        assert "state code" in r.message.lower()

    def test_invalid_state_code_99(self):
        r = validate_ulpin("99421852073856")
        assert not r.valid


class TestULPINNormalization:
    def test_strips_spaces(self):
        assert normalize_ulpin("15 42 1234 5678") == "154212345678"

    def test_strips_dashes(self):
        assert normalize_ulpin("15-42-12345678") == "154212345678"

    def test_empty(self):
        assert normalize_ulpin("") == ""

    def test_none_like(self):
        assert normalize_ulpin(None) == ""


class TestULPINLinking:
    def test_exact_match_grouped(self):
        # Two distinct valid ULPINs that differ only slightly (within tolerance)
        # The same ULPIN twice deduplicates to one entry — that's correct.
        groups = link_ulpins(["15421852073856"])
        assert len(groups) == 1
        # Different ULPINs with same prefix: both in one group when within tolerance
        groups2 = link_ulpins(["15421852073856", "15421852073880"])
        # They have the same state+district prefix; difference in last digits
        # 73856 vs 73880 = diff of 24 < 50 → same group
        assert len(groups2) == 1

    def test_different_state_not_linked(self):
        # Different state codes → different groups
        groups = link_ulpins(["15421852073856", "27421852073856"])
        assert len(groups) == 2

    def test_invalid_ulpins_excluded(self):
        groups = link_ulpins(["invalid", "15421852073856"])
        assert len(groups) == 1
        assert groups[0][0] == "15421852073856"

    def test_empty_list(self):
        assert link_ulpins([]) == []

    def test_none_values_handled(self):
        groups = link_ulpins([None, "15421852073856", None])
        assert len(groups) == 1


class TestULPINExtraction:
    def test_extracts_from_ulpin_key(self):
        attrs = {"ulpin": "15421852073856", "name": "Parcel A"}
        result = extract_ulpin_from_attributes(attrs)
        assert result == "15421852073856"

    def test_extracts_from_bhu_aadhaar(self):
        attrs = {"bhu_aadhaar": "15421852073856"}
        result = extract_ulpin_from_attributes(attrs)
        assert result == "15421852073856"

    def test_invalid_value_not_extracted(self):
        attrs = {"ulpin": "INVALID", "name": "Test"}
        result = extract_ulpin_from_attributes(attrs)
        assert result is None

    def test_empty_dict(self):
        assert extract_ulpin_from_attributes({}) is None


class TestDemoIdentifier:
    """Tests for the DEMO-ONLY spatial identifier (not official ULPIN)."""

    def test_14_chars(self):
        r = generate_demo_identifier(73.8567, 18.5204)
        assert len(r.demo_id) == 14
        assert r.demo_id.isdigit()

    def test_not_official(self):
        r = generate_demo_identifier(73.8567, 18.5204)
        assert not r.is_official_ulpin
        assert "DEMO" in r.disclaimer

    def test_deterministic(self):
        r1 = generate_demo_identifier(73.8567, 18.5204)
        r2 = generate_demo_identifier(73.8567, 18.5204)
        assert r1.demo_id == r2.demo_id

    def test_different_coords_different_id(self):
        r1 = generate_demo_identifier(73.8567, 18.5204)  # Pune
        r2 = generate_demo_identifier(77.2167, 28.6448)  # Delhi
        assert r1.demo_id != r2.demo_id

    def test_state_code_embedded(self):
        r = generate_demo_identifier(73.8567, 18.5204, state_code="15", district_code="42")
        assert r.demo_id.startswith("1542")

    def test_invalid_coords_raise(self):
        import pytest
        with pytest.raises(ValueError):
            generate_demo_identifier(200.0, 100.0)

    def test_from_geometry(self):
        geom = {
            "type": "Polygon",
            "coordinates": [[[73.85, 18.52], [73.86, 18.52],
                              [73.86, 18.53], [73.85, 18.53], [73.85, 18.52]]]
        }
        r = demo_identifier_from_geometry(geom)
        assert r is not None
        assert len(r.demo_id) == 14
        assert not r.is_official_ulpin
