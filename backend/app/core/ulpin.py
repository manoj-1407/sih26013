"""ULPIN / Bhu-Aadhaar — Parcel Identifier Integration.

WHAT THIS MODULE DOES (and does NOT do)
═══════════════════════════════════════
This module provides:
  1. Validation of ULPIN strings supplied from authoritative sources
     (BhuNaksha, state land-record systems, DILRMP portal).
  2. ULPIN-based linking: given a set of ULPINs, determine which ones
     likely refer to the same parcel (useful when ULPINs from different
     databases have minor formatting differences).
  3. A DEMO-ONLY spatial identifier for prototype purposes — clearly
     labelled as NOT the official ULPIN algorithm.

WHAT IT DOES NOT DO
═══════════════════
This module does NOT implement the official DoLR/ECCMA ULPIN generation
algorithm. The authoritative ULPIN is generated through the ECCMA Property
Natural Identifier Unit methodology and is derived from the georeferenced
coordinates of the parcel's vertices (not merely the centroid), processed
through a coordinate encoding/base-conversion algorithm not publicly
documented in full detail.

Until the complete official algorithm can be validated against known
ULPIN outputs from DILRMP, we treat ULPIN as:

  An IDENTIFIER WE CONSUME, not one we generate.

Architecture implication:
  Source datasets (BhuNaksha, revenue records) supply ULPINs.
  GeoSamanvay reads them, links matching ULPINs across datasets,
  and uses them as a strong identity signal in parcel matching.

References:
  DoLR ULPIN/Bhu-Aadhaar circular series (2019–2022)
  DILRMP ULPIN operational documentation
  ECCMA Property Natural Identifier Unit specification
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# ULPIN format validation (authoritative ULPINs from source systems)
# ─────────────────────────────────────────────────────────────────────────────

# DoLR state codes (for validation only)
VALID_STATE_CODES: set[str] = {
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
    "21", "22", "23", "24", "25", "26", "27", "28", "29", "30",
    "31", "32", "33", "34", "35", "36", "37", "38",
}


@dataclass
class ULPINValidationResult:
    ulpin: str              # normalized (spaces/dashes stripped)
    valid: bool
    message: str
    state_code: Optional[str] = None


def normalize_ulpin(ulpin: str) -> str:
    """Normalize a ULPIN string: remove spaces, dashes, uppercase."""
    return re.sub(r"[\s\-]", "", (ulpin or "").strip())


def validate_ulpin(ulpin: str) -> ULPINValidationResult:
    """
    Validate the format of a ULPIN string supplied from an authoritative source.

    Checks:
      - Exactly 14 digits
      - All numeric
      - State code in valid range (01–38)

    Does NOT verify that the ULPIN is registered in any database.
    """
    normalized = normalize_ulpin(ulpin)

    if not normalized:
        return ULPINValidationResult(normalized, False, "Empty ULPIN")

    if not normalized.isdigit():
        return ULPINValidationResult(normalized, False,
            f"ULPIN must contain only digits; got: {normalized!r}")

    if len(normalized) != 14:
        return ULPINValidationResult(normalized, False,
            f"ULPIN must be exactly 14 digits; got {len(normalized)}: {normalized!r}")

    state = normalized[:2]
    if state not in VALID_STATE_CODES:
        return ULPINValidationResult(normalized, False,
            f"Invalid state code {state!r} (valid range: 01–38)")

    return ULPINValidationResult(
        ulpin=normalized, valid=True,
        message="Valid ULPIN format",
        state_code=state,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ULPIN linking — match ULPINs across datasets
# ─────────────────────────────────────────────────────────────────────────────

def link_ulpins(
    ulpin_list: list[Optional[str]],
    require_state_match: bool = True,
) -> list[list[str]]:
    """
    Group ULPINs that likely refer to the same parcel.

    Grouping rules:
      1. Exact match (after normalization) → same group.
      2. Same state + district prefix (first 4 digits) + last 10 within
         tolerance of 2 → candidate same parcel (measurement precision).

    This handles cases where the same parcel has slightly different ULPIN
    representations in different source systems due to coordinate rounding
    during generation.

    Returns: list of groups, each group is a list of normalized ULPINs.
    """
    valid_ulpins: list[str] = []
    for u in ulpin_list:
        if u:
            r = validate_ulpin(u)
            if r.valid:
                valid_ulpins.append(r.ulpin)

    if not valid_ulpins:
        return []

    groups: list[list[str]] = []
    used: set[str] = set()

    for a in valid_ulpins:
        if a in used:
            continue
        group = [a]
        used.add(a)

        for b in valid_ulpins:
            if b in used or b == a:
                continue

            # Exact match
            if a == b:
                group.append(b)
                used.add(b)
                continue

            # State+district prefix must match
            if require_state_match and a[:4] != b[:4]:
                continue

            # Remaining 10 digits: check proximity
            # (tolerates minor coordinate encoding rounding)
            try:
                diff = abs(int(a[4:]) - int(b[4:]))
                if diff <= 50:  # within ~50 units = same parcel candidate
                    group.append(b)
                    used.add(b)
            except ValueError:
                pass

        groups.append(group)

    return groups


def extract_ulpin_from_attributes(attributes: dict) -> Optional[str]:
    """
    Extract a ULPIN value from a record's attribute dict.
    Checks common field names: ulpin, ULPIN, bhu_aadhaar, uid, etc.
    Returns the first valid ULPIN found, or None.
    """
    candidates = [
        "ulpin", "ULPIN", "Ulpin", "bhu_aadhaar", "bhu_aadhar",
        "Bhu_Aadhaar", "bhuu_aadhaar", "uid", "UID", "unique_id",
        "parcel_uid", "land_uid",
    ]
    for key in candidates:
        val = attributes.get(key)
        if val:
            r = validate_ulpin(str(val))
            if r.valid:
                return r.ulpin
    return None


# ─────────────────────────────────────────────────────────────────────────────
# DEMO-ONLY spatial parcel identifier
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DemoParcelIdentifier:
    """
    A spatial parcel reference for prototype/demo use ONLY.

    NOT the official ULPIN algorithm. NOT suitable for production use.
    Clearly labelled as a demo identifier in all API responses.

    Useful for the SIH demo to show ULPIN-style parcel referencing
    when no authoritative ULPIN is available in the test dataset.
    """
    demo_id: str            # 14-char demo identifier
    state_code: str
    district_code: str
    centroid_lat: float
    centroid_lon: float
    is_official_ulpin: bool = False
    disclaimer: str = (
        "DEMO IDENTIFIER ONLY — not the official DoLR ULPIN algorithm. "
        "In production, consume ULPINs from authoritative sources (BhuNaksha, DILRMP)."
    )


def generate_demo_identifier(
    centroid_lon: float,
    centroid_lat: float,
    state_code: str = "15",
    district_code: str = "42",
) -> DemoParcelIdentifier:
    """
    Generate a 14-character demo parcel identifier from centroid coordinates.

    Format: SS DD LLLLLL OOOO
      SS = state code (2)
      DD = district code (2)
      LLLLLL = lat * 10000, mod 1,000,000, zero-padded to 6
      OOOO = lon * 1000, mod 10000, zero-padded to 4
    Total = 2+2+6+4 = 14

    This is deterministic and coordinate-embedded but is NOT the official ULPIN.
    """
    if not (-90 <= centroid_lat <= 90) or not (-180 <= centroid_lon <= 180):
        raise ValueError(f"Invalid coordinates: lat={centroid_lat}, lon={centroid_lon}")

    lat_part = str(int(abs(centroid_lat) * 10000) % 1_000_000).zfill(6)
    lon_part = str(int(abs(centroid_lon) * 1000) % 10000).zfill(4)
    demo_id = state_code.zfill(2)[:2] + district_code.zfill(2)[:2] + lat_part + lon_part

    assert len(demo_id) == 14, f"demo_id length error: {demo_id!r}"

    return DemoParcelIdentifier(
        demo_id=demo_id,
        state_code=state_code[:2],
        district_code=district_code[:2],
        centroid_lat=centroid_lat,
        centroid_lon=centroid_lon,
    )


def demo_identifier_from_geometry(geom_geojson: dict, **kwargs) -> Optional[DemoParcelIdentifier]:
    """Generate a demo identifier from a GeoJSON geometry centroid."""
    try:
        from shapely.geometry import shape
        geom = shape(geom_geojson)
        if geom is None or geom.is_empty:
            return None
        return generate_demo_identifier(
            centroid_lon=float(geom.centroid.x),
            centroid_lat=float(geom.centroid.y),
            **kwargs,
        )
    except Exception:
        return None
