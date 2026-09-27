"""Multilingual / Transliteration-Aware Owner Name Matching.

The Indian land-record ecosystem stores owner names in multiple forms:
  - Devanagari script (Hindi/Marathi RoR)
  - Roman transliteration (municipal GIS, survey records)
  - Inconsistent transliteration schemes (ITRANS, HK, ISO-15919, colloquial)
  - Honorifics (Shri, Smt., Sri, Late)
  - Patronymic variations (s/o, d/o, w/o, son of)

Key insight: "Ramesh Kumar", "Ramesh K.", "श्री रमेश कुमार", "Remesh Kumaar"
are all likely the same person in a land-record context.

We solve this at three levels:
  1. Normalization: strip honorifics, patronymics, punctuation, case
  2. Phonetic matching: custom Soundex variant tuned for Indian names
  3. Edit-distance: RapidFuzz token_set_ratio for fuzzy agreement

This is a direct competitive response to A.L.I.G.N.'s IndicSoundex feature.
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from rapidfuzz import fuzz


# ─────────────────────────────────────────────────────────────────────────────
# Honorific / relational stripping
# ─────────────────────────────────────────────────────────────────────────────

# Common honorifics in Indian land records (case-insensitive)
_HONORIFICS = {
    "shri", "smt", "smt.", "sri", "sh", "sh.", "late", "mr", "mrs", "dr",
    "prof", "km", "ku", "kumari", "col", "adv", "er",
    # Hindi/Marathi
    "श्री", "श्रीमती", "सौ", "सौ.", "स्व",
}

# Relational suffixes / patronymic phrases
_RELATIONAL_RE = re.compile(
    r"\b(s/?o|d/?o|w/?o|son of|daughter of|wife of|wd of|"
    r"putra|putri|patni|widow of|s\.o|d\.o|w\.o)\b",
    re.IGNORECASE,
)


def _strip_diacritics(text: str) -> str:
    """Normalize unicode: NFD decompose, strip combining marks, recompose."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _romanize_devanagari(text: str) -> str:
    """
    Approximate Devanagari → Roman transliteration using character substitution.
    Not a complete ITRANS/ISO-15919 engine, but handles the most common
    characters that appear in land-record owner names.
    """
    table = {
        "अ": "a", "आ": "aa", "इ": "i", "ई": "ii", "उ": "u", "ऊ": "uu",
        "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au",
        "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
        "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
        "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
        "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
        "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
        "य": "y", "र": "r", "ल": "l", "व": "v", "श": "sh",
        "ष": "sh", "स": "s", "ह": "h",
        "क्ष": "ksh", "त्र": "tr", "ज्ञ": "gn",
        "ा": "aa", "ि": "i", "ी": "ii", "ु": "u", "ू": "uu",
        "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
        "्": "", "ं": "n", "ः": "h", "ँ": "n", "़": "",
        "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
        "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
    }
    result = []
    i = 0
    while i < len(text):
        # Try 2-char combo first (क्ष, त्र, ज्ञ)
        two = text[i:i+2]
        if two in table:
            result.append(table[two])
            i += 2
        elif text[i] in table:
            result.append(table[text[i]])
            i += 1
        else:
            result.append(text[i])
            i += 1
    return "".join(result)


def _normalize_name(name: str) -> str:
    """
    Full normalization pipeline:
    1. Romanize Devanagari (if present)
    2. Strip diacritics
    3. Strip honorifics
    4. Strip relational phrases
    5. Lowercase, remove punctuation, collapse whitespace
    """
    if not name:
        return ""

    # Detect and romanize Devanagari
    has_devanagari = any("\u0900" <= c <= "\u097f" for c in name)
    if has_devanagari:
        name = _romanize_devanagari(name)

    # Strip diacritics from Roman
    name = _strip_diacritics(name)

    # Lowercase
    name = name.lower()

    # Strip honorifics (whole words)
    words = name.split()
    words = [w for w in words if w.rstrip(".") not in _HONORIFICS]
    name = " ".join(words)

    # Strip relational phrases (s/o, d/o, etc.) — everything after
    name = _RELATIONAL_RE.split(name)[0]

    # Remove punctuation except spaces
    name = re.sub(r"[^a-z0-9\s]", " ", name)

    # Collapse whitespace
    name = " ".join(name.split())

    return name


# ─────────────────────────────────────────────────────────────────────────────
# Indian Phonetic Soundex (IndicSoundex variant)
# ─────────────────────────────────────────────────────────────────────────────

# Phonetic group map for Indian name sounds
# Groups similar-sounding consonants together
_PHONETIC_MAP: dict[str, str] = {
    "b": "1", "bh": "1", "p": "1", "ph": "1", "v": "1", "w": "1",
    "c": "2", "ch": "2", "g": "2", "gh": "2", "j": "2", "jh": "2",
    "k": "2", "kh": "2", "q": "2",
    "d": "3", "dh": "3", "t": "3", "th": "3",
    "l": "4", "r": "4",
    "m": "5", "n": "5",
    "f": "6", "s": "6", "sh": "6", "x": "6", "z": "6",
    "h": "0", "y": "0",
}


def _indic_soundex(name: str) -> str:
    """
    Indian-context phonetic code.
    Similar to Soundex but tuned for Indian consonant clusters.
    Returns a 5-char code: first_letter + 4 digit groups.
    """
    name = name.strip().lower()
    if not name:
        return "0000"

    # Retain first char
    code = [name[0].upper()]
    prev = ""
    i = 1

    while len(code) < 5 and i < len(name):
        # Try 2-char match
        two = name[i:i+2]
        one = name[i]

        if two in _PHONETIC_MAP:
            digit = _PHONETIC_MAP[two]
            if digit != "0" and digit != prev:
                code.append(digit)
                prev = digit
            i += 2
        elif one in _PHONETIC_MAP:
            digit = _PHONETIC_MAP[one]
            if digit != "0" and digit != prev:
                code.append(digit)
                prev = digit
            i += 1
        else:
            i += 1

    # Pad to 5 chars
    code = (code + ["0"] * 5)[:5]
    return "".join(code)


# ─────────────────────────────────────────────────────────────────────────────
# Name matching result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class NameMatchResult:
    name_a: str
    name_b: str
    normalized_a: str
    normalized_b: str
    soundex_a: str
    soundex_b: str
    soundex_match: bool
    fuzzy_score: float          # 0-100 RapidFuzz token_set_ratio
    overall_similarity: float   # 0-1 composite
    match_level: str            # EXACT / HIGH / MEDIUM / LOW / NO_MATCH
    explanation: str


def compare_names(name_a: Optional[str], name_b: Optional[str]) -> NameMatchResult:
    """
    Compare two owner/reference names using multi-level matching.
    Returns a NameMatchResult with scores and explanation.
    """
    na = _normalize_name(name_a or "")
    nb = _normalize_name(name_b or "")

    sa = _indic_soundex(na)
    sb = _indic_soundex(nb)
    soundex_match = sa == sb and sa != "0000"

    if not na or not nb:
        return NameMatchResult(
            name_a or "", name_b or "", na, nb, sa, sb,
            False, 0.0, 0.0, "NO_MATCH",
            "One or both names empty after normalization",
        )

    # Exact match after normalization
    if na == nb:
        return NameMatchResult(
            name_a, name_b, na, nb, sa, sb,
            soundex_match, 100.0, 1.0, "EXACT",
            f"Exact match after normalization: '{na}'",
        )

    # Fuzzy score (handles abbreviations, word reordering, typos)
    fuzzy = fuzz.token_set_ratio(na, nb)

    # Composite: 70% fuzzy + 30% soundex bonus
    soundex_bonus = 15 if soundex_match else 0
    composite = min(1.0, (fuzzy * 0.7 + soundex_bonus) / 100.0)

    # Classify
    if fuzzy >= 90:
        level = "HIGH"
        explanation = (
            f"High similarity ({fuzzy}%): likely transliteration variation. "
            f"'{name_a}' ↔ '{name_b}'"
        )
    elif fuzzy >= 75:
        level = "MEDIUM"
        explanation = (
            f"Moderate similarity ({fuzzy}%): possible same person with name variant. "
            f"Soundex: {sa}↔{sb}"
        )
    elif soundex_match and fuzzy >= 50:
        level = "MEDIUM"
        explanation = (
            f"Phonetically similar (soundex {sa}={sb}) despite spelling differences ({fuzzy}%). "
            "May be same name in different script/transliteration scheme."
        )
    elif fuzzy >= 50:
        level = "LOW"
        explanation = (
            f"Weak similarity ({fuzzy}%). Different names or significant variation. "
            "Manual review recommended."
        )
    else:
        level = "NO_MATCH"
        explanation = f"No meaningful name similarity ({fuzzy}%). Likely different owners."

    return NameMatchResult(
        name_a or "", name_b or "", na, nb, sa, sb,
        soundex_match, float(fuzzy), composite, level, explanation,
    )


def best_owner_similarity(names_a: list[str], names_b: list[str]) -> NameMatchResult:
    """
    Best match across two lists of names (handles joint-ownership records).
    Returns the highest-scoring pair.
    """
    best: Optional[NameMatchResult] = None
    for a in names_a:
        for b in names_b:
            r = compare_names(a, b)
            if best is None or r.overall_similarity > best.overall_similarity:
                best = r
    return best or compare_names("", "")
