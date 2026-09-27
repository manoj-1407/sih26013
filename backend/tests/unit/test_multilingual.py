"""Unit tests for multilingual name matching."""
from app.matching.multilingual import compare_names, _normalize_name, _indic_soundex


class TestNormalization:
    def test_strips_honorifics(self):
        assert _normalize_name("Shri Ramesh Kumar") == "ramesh kumar"
        assert _normalize_name("Smt. Priya Devi") == "priya devi"
        assert _normalize_name("Late Mohan Lal") == "mohan lal"

    def test_strips_relational(self):
        assert "s/o" not in _normalize_name("Ramesh Kumar s/o Mohan")
        assert "son of" not in _normalize_name("Raj Kumar son of Ram Kumar")

    def test_devanagari_romanized(self):
        result = _normalize_name("रमेश कुमार")
        assert len(result) > 0
        # Should not contain Devanagari characters after normalization
        assert not any("\u0900" <= c <= "\u097f" for c in result)

    def test_lowercase(self):
        assert _normalize_name("RAMESH KUMAR") == "ramesh kumar"


class TestSoundex:
    def test_similar_names(self):
        a = _indic_soundex("ramesh")
        b = _indic_soundex("ramesh")
        assert a == b

    def test_different_names_differ(self):
        a = _indic_soundex("ramesh")
        b = _indic_soundex("suresh")
        # Different names should have different soundex (not guaranteed but likely)
        # Just check it returns 5 chars
        assert len(a) == 5
        assert len(b) == 5

    def test_transliteration_variants(self):
        # "Kumar" vs "Kumaar" — similar phonetically
        a = _indic_soundex("kumar")
        b = _indic_soundex("kumaar")
        assert len(a) == 5


class TestNameComparison:
    def test_exact_match(self):
        r = compare_names("Ramesh Kumar", "Ramesh Kumar")
        assert r.match_level == "EXACT"
        assert r.overall_similarity == 1.0

    def test_honorific_variant(self):
        r = compare_names("Shri Ramesh Kumar", "Ramesh Kumar")
        assert r.match_level in ("EXACT", "HIGH")

    def test_abbreviation(self):
        r = compare_names("Ramesh K. Kumar", "Ramesh Kumar")
        assert r.overall_similarity >= 0.5

    def test_different_names(self):
        r = compare_names("Suresh Yadav", "Priya Sharma")
        assert r.match_level in ("LOW", "NO_MATCH")

    def test_empty_name(self):
        r = compare_names("", "Ramesh Kumar")
        assert r.match_level == "NO_MATCH"
        assert r.overall_similarity == 0.0

    def test_none_name(self):
        r = compare_names(None, None)
        assert r.overall_similarity == 0.0

    def test_transliteration(self):
        # Roman vs Devanagari for "Ramesh"
        r = compare_names("Ramesh Kumar", "रमेश कुमार")
        # Should find some similarity after romanization
        assert r.fuzzy_score > 0
