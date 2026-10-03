"""Schema normalization: maps heterogeneous source field names to canonical fields.

Each government dataset uses different field names for the same concept:
  Revenue: Khasra_No, Owner_Name, Area
  Municipal: Property_ID, Owner, Plot_Area
  Survey: Parcel_ID, Measured_Area, Use

This module maintains a mapping table and applies fuzzy matching
for unknown fields.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import re

from rapidfuzz import fuzz


# ─────────────────────────────────────────────────────────────────────────────
# Canonical field names
# ─────────────────────────────────────────────────────────────────────────────

CANONICAL_FIELDS = {
    "parcel_reference",     # primary identifier (khasra no, property id, etc.)
    "ulpin",                # ULPIN if present
    "owner_reference",      # owner name / reference
    "area",                 # numeric area value
    "area_unit",            # sqm / sqft / acre / hectare
    "land_use",             # land use / usage type
    "address",              # address if present
    "ward",                 # ward / zone
    "village",              # village / locality name
    "survey_number",        # survey / mutation number
    "mutation_date",        # date of last mutation
    "capture_date",         # when this record was captured/surveyed
}


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic mapping rules (source_field_lower → canonical_field)
# ─────────────────────────────────────────────────────────────────────────────

_FIELD_ALIASES: dict[str, str] = {
    # parcel_reference
    "khasra_no": "parcel_reference",
    "khasra": "parcel_reference",
    "khasra_number": "parcel_reference",
    "property_id": "parcel_reference",
    "propertyid": "parcel_reference",
    "parcel_id": "parcel_reference",
    "parcelid": "parcel_reference",
    "plot_no": "parcel_reference",
    "plot_number": "parcel_reference",
    "survey_no": "parcel_reference",
    "khata_no": "parcel_reference",
    "khata_number": "parcel_reference",
    "holding_no": "parcel_reference",
    "gat_no": "parcel_reference",
    "dag_no": "parcel_reference",
    # ulpin
    "ulpin": "ulpin",
    "bhu_aadhaar": "ulpin",
    "bhu_aadhar": "ulpin",
    "uid": "ulpin",
    # owner_reference
    "owner_name": "owner_reference",
    "owner": "owner_reference",
    "khatadar": "owner_reference",
    "bhumiswami": "owner_reference",
    "occupant": "owner_reference",
    "applicant_name": "owner_reference",
    "holder_name": "owner_reference",
    # area
    "area": "area",
    "plot_area": "area",
    "measured_area": "area",
    "parcel_area": "area",
    "extent": "area",
    "area_sqm": "area",
    "area_sqft": "area",
    "area_ha": "area",
    "area_acre": "area",
    "bhumi_area": "area",
    # area_unit
    "unit": "area_unit",
    "area_unit": "area_unit",
    # land_use
    "land_use": "land_use",
    "use": "land_use",
    "usage_type": "land_use",
    "land_type": "land_use",
    "land_class": "land_use",
    "land_category": "land_use",
    "classification": "land_use",
    "land_classification": "land_use",
    "zone": "land_use",
    "use_type": "land_use",
    # address
    "address": "address",
    "postal_address": "address",
    "full_address": "address",
    # ward
    "ward": "ward",
    "ward_no": "ward",
    "ward_number": "ward",
    "ward_name": "ward",
    "zone_no": "ward",
    # village
    "village": "village",
    "village_name": "village",
    "locality": "village",
    "mohalla": "village",
    "gram": "village",
    # survey_number
    "survey_number": "survey_number",
    "mutation_no": "survey_number",
    "mutation_number": "survey_number",
    # mutation_date
    "mutation_date": "mutation_date",
    "date_of_mutation": "mutation_date",
    "last_updated": "mutation_date",
    # capture_date
    "capture_date": "capture_date",
    "survey_date": "capture_date",
    "date_of_survey": "capture_date",
    "acquisition_date": "capture_date",
    "date": "capture_date",
    "timestamp": "capture_date",
    # DSM/DTM elevation fields
    "dsm_mean_m": "dsm_mean_m",
    "dsm_mean": "dsm_mean_m",
    "dsm_min_m": "dsm_min_m",
    "dsm_max_m": "dsm_max_m",
    "dtm_mean_m": "dtm_mean_m",
    "dtm_mean": "dtm_mean_m",
    "dtm_min_m": "dtm_min_m",
    "dtm_max_m": "dtm_max_m",
    "building_height_m": "estimated_building_height_m",
    "estimated_building_height_m": "estimated_building_height_m",
    "has_structure": "has_structure",
    "resolution_m": "resolution_m",
    "elevation_source_type": "elevation_source_type",
    # GNSS fields
    "gnss_method": "gnss_method",
    "horizontal_accuracy_m": "horizontal_accuracy_m",
    "vertical_accuracy_m": "vertical_accuracy_m",
    "pdop": "pdop",
    "cors_station": "cors_station",
    "baseline_length_km": "baseline_length_km",
    "mark_type": "mark_type",
    # Ground truth fields
    "gt_category": "gt_category",
    "gt_confidence": "gt_confidence",
    "observed_value": "observed_value",
    "contradicts_source": "contradicts_source",
    "supports_source": "supports_source",
}

# Area unit normalization: always store in sqm
_AREA_UNIT_MULTIPLIERS: dict[str, float] = {
    "sqm": 1.0, "m2": 1.0, "m²": 1.0,
    "sqft": 0.0929, "sqfeet": 0.0929, "ft2": 0.0929,
    "acre": 4046.86, "acres": 4046.86,
    "hectare": 10000.0, "ha": 10000.0,
    "sqyd": 0.8361, "sqyard": 0.8361,
    "guntha": 101.17, "gunta": 101.17,
    "cent": 40.47,
}


@dataclass
class SchemaMappingResult:
    canonical: dict                         # {canonical_field: value}
    unmapped: dict                          # {original_field: value}
    mapping_used: dict[str, str]            # {original_field: canonical_field}
    mapping_method: dict[str, str]          # {original_field: "alias"|"fuzzy"|"unmapped"}
    area_sqm: Optional[float]               # normalized area in sqm


def _normalize_field_name(name: str) -> str:
    """Lowercase + strip spaces/special chars."""
    return re.sub(r"[^a-z0-9_]", "_", name.lower().strip())


def _fuzzy_match_canonical(field_name: str, threshold: int = 75) -> Optional[str]:
    """Fuzzy-match a field name against canonical field aliases."""
    normalized = _normalize_field_name(field_name)
    best_score = 0
    best_canonical = None
    for alias, canonical in _FIELD_ALIASES.items():
        score = fuzz.ratio(normalized, alias)
        if score > best_score:
            best_score = score
            best_canonical = canonical
    if best_score >= threshold:
        return best_canonical
    return None


def _normalize_area(value, unit_hint: Optional[str] = None) -> Optional[float]:
    """Convert area value to sqm."""
    try:
        numeric = float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None
    if unit_hint:
        unit_key = unit_hint.lower().strip()
        multiplier = _AREA_UNIT_MULTIPLIERS.get(unit_key, 1.0)
        return numeric * multiplier
    return numeric


def normalize_attributes(
    attributes: dict,
    source_type: str = "UNKNOWN",
    fuzzy_threshold: int = 75,
) -> SchemaMappingResult:
    """
    Map source attributes to canonical fields.
    Uses deterministic aliases first, fuzzy matching for remainder.
    """
    canonical: dict = {}
    unmapped: dict = {}
    mapping_used: dict[str, str] = {}
    mapping_method: dict[str, str] = {}
    raw_area = None
    raw_area_unit = None

    for field_name, value in attributes.items():
        normalized_name = _normalize_field_name(field_name)
        # Deterministic alias lookup
        if normalized_name in _FIELD_ALIASES:
            target = _FIELD_ALIASES[normalized_name]
            canonical[target] = value
            mapping_used[field_name] = target
            mapping_method[field_name] = "alias"
            if target == "area":
                raw_area = value
            elif target == "area_unit":
                raw_area_unit = str(value)
        else:
            # Fuzzy match
            fuzzy_target = _fuzzy_match_canonical(field_name, fuzzy_threshold)
            if fuzzy_target:
                canonical.setdefault(fuzzy_target, value)  # don't overwrite exact matches
                mapping_used[field_name] = fuzzy_target
                mapping_method[field_name] = "fuzzy"
            else:
                unmapped[field_name] = value
                mapping_method[field_name] = "unmapped"

    # Normalize area to sqm
    area_sqm_val = None
    if raw_area is not None:
        area_sqm_val = _normalize_area(raw_area, raw_area_unit)
        if area_sqm_val is not None:
            canonical["area_sqm_normalized"] = round(area_sqm_val, 3)

    return SchemaMappingResult(
        canonical=canonical,
        unmapped=unmapped,
        mapping_used=mapping_used,
        mapping_method=mapping_method,
        area_sqm=area_sqm_val,
    )
