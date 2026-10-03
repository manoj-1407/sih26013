"""Ground Truth (GT) Observation Adapter — PS26013 Gap Closure.

Integrates field-verified ground truth observations into the
GeoSamanvay reconciliation pipeline.

WHAT WE DO:
  - Accept GT observations from field surveyors as GeoJSON / CSV / JSON
  - Model: location, observed feature category, operator, confidence, notes
  - Feed as independent evidence into the provenance graph (separate origin)
  - Enable GT observations to support or contradict AI/satellite-derived features
  - GT is the highest-confidence non-GPS evidence source

WHAT WE DON'T DO:
  - Photo management / drone imagery  (use imagery_adapter for that)
  - GNSS positioning (use gnss_adapter for that)
  - Legal survey operations

GT observation categories (from PS26013 context):
  BOUNDARY_MARK      — physical boundary demarcation visible on ground
  BUILDING_PRESENT   — structure confirmed at location
  NO_BUILDING        — no structure confirmed (contradicts AI extraction)
  LAND_USE           — observed land use (residential / commercial / etc.)
  ENCROACHMENT       — encroachment onto neighbouring parcel or ROW
  ACCESS_ROAD        — road/pathway confirmed
  UTILITY_PRESENT    — utility infrastructure confirmed
  WATER_BODY         — water body / drainage confirmed
  OPEN_LAND          — open/vacant land confirmed
  OTHER              — any other observed feature

Architecture:
  Field survey (GeoJSON / CSV / paper digitised)
          ↓
    GroundTruthAdapter
          ↓
    Canonical features with observer confidence + category
          ↓
    Standard ingestor pipeline (SourceType.GROUND_TRUTH)
          ↓
    Matching / conflict / provenance engines

In the provenance graph, GT observations get their own independent origin
node (ORIG-GT-*), which gives them maximum independence bonus when combined
with cadastral/satellite sources.
"""
from __future__ import annotations
import csv
import io
import json
import uuid
from dataclasses import dataclass, field
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Valid observation categories
# ─────────────────────────────────────────────────────────────────────────────

GT_CATEGORIES = {
    "boundary_mark", "building_present", "no_building", "land_use",
    "encroachment", "access_road", "utility_present", "water_body",
    "open_land", "other",
}

# Quality weight for GT observations (field-verified = very high confidence)
GT_QUALITY_WEIGHT = 0.95


@dataclass
class GTObservation:
    """A single field-verified ground truth observation."""
    obs_id: str
    geometry_geojson: dict           # Point, Polygon, or LineString
    category: str                    # from GT_CATEGORIES
    observed_value: Optional[str]    # e.g. "Residential" for LAND_USE category
    confidence: float                # 0.0–1.0 — observer's stated confidence
    operator: Optional[str]          # Field observer name/ID
    observation_date: Optional[str]  # ISO date
    notes: Optional[str]
    linked_parcel_hint: Optional[str]  # Khasra/property ID if known
    contradicts_source: Optional[str]  # Source type it contradicts, if noted
    supports_source: Optional[str]     # Source type it supports, if noted
    photo_reference: Optional[str]    # Reference to photo evidence if available


@dataclass
class GTEvidence:
    """Ground truth evidence ready for ingestor pipeline."""
    observations: list[GTObservation]
    features: list[dict]
    provenance_nodes: list[dict]
    evidence_note: str
    operator: Optional[str] = None


def _normalise_category(raw: Optional[str]) -> str:
    if not raw:
        return "other"
    r = str(raw).lower().strip().replace(" ", "_").replace("-", "_")
    for cat in GT_CATEGORIES:
        if r == cat or r.startswith(cat[:6]):
            return cat
    return "other"


def _obs_to_feature(obs: GTObservation, prov_ds_id: str) -> dict:
    props = {
        "parcel_reference": obs.linked_parcel_hint,
        "gt_observation_id": obs.obs_id,
        "gt_category": obs.category,
        "observed_value": obs.observed_value,
        "gt_confidence": str(obs.confidence),
        "operator": obs.operator,
        "notes": obs.notes,
        "contradicts_source": obs.contradicts_source,
        "supports_source": obs.supports_source,
        "photo_reference": obs.photo_reference,
        "derived_from": "ground_truth_survey",
        # Land-use for category land_use
        "land_use": obs.observed_value if obs.category == "land_use" else None,
        # has_structure inference
        "has_structure": (
            "true" if obs.category == "building_present" else
            "false" if obs.category == "no_building" else None
        ),
    }
    return {
        "geometry": obs.geometry_geojson,
        "properties": {k: (str(v) if v is not None else None) for k, v in props.items()},
        "capture_timestamp": obs.observation_date,
        "provenance_node_id": prov_ds_id,
    }


def adapt_gt_geojson(
    geojson: dict | str,
    operator: Optional[str] = None,
    default_confidence: float = 0.90,
) -> GTEvidence:
    """
    Parse a GeoJSON FeatureCollection of GT observations.

    Expected feature properties:
      obs_id / id, category, value / observed_value,
      confidence (0–1), operator, date / observation_date,
      parcel / khasra_no, notes, contradicts, supports, photo
    """
    if isinstance(geojson, str):
        geojson = json.loads(geojson)

    rows = []
    for feat in geojson.get("features", []):
        geom = feat.get("geometry")
        props = dict(feat.get("properties") or {})
        props["_geometry"] = geom
        rows.append(props)

    return _adapt_rows(rows, operator, default_confidence)


def adapt_gt_csv(
    csv_data: str,
    operator: Optional[str] = None,
    default_confidence: float = 0.90,
) -> GTEvidence:
    """
    Parse a GT observation CSV.

    Expected columns (case-insensitive):
      obs_id, lat, lon, category, value, confidence, operator,
      date, parcel/khasra_no, notes, contradicts, supports, photo
    """
    reader = csv.DictReader(io.StringIO(csv_data.strip()))
    rows = []
    for row in reader:
        row_lower = {k.lower().strip(): v for k, v in row.items()}
        lat = _safe_float(row_lower.get("lat") or row_lower.get("latitude"))
        lon = _safe_float(row_lower.get("lon") or row_lower.get("longitude"))
        if lat is None or lon is None:
            continue
        row_lower["_geometry"] = {"type": "Point", "coordinates": [lon, lat]}
        rows.append(row_lower)

    return _adapt_rows(rows, operator, default_confidence)


def adapt_gt_json(
    data: list[dict] | str,
    operator: Optional[str] = None,
    default_confidence: float = 0.90,
) -> GTEvidence:
    """Parse a list of GT observation dicts (or JSON string)."""
    if isinstance(data, str):
        data = json.loads(data)
    return _adapt_rows(data, operator, default_confidence)


def _adapt_rows(
    rows: list[dict],
    operator: Optional[str],
    default_confidence: float,
) -> GTEvidence:
    prov_origin_id = f"ORIG-GT-{uuid.uuid4().hex[:8].upper()}"
    prov_ds_id = f"DS-GT-{uuid.uuid4().hex[:8].upper()}"

    observations: list[GTObservation] = []

    for i, row in enumerate(rows):
        row_lower = {k.lower().strip(): v for k, v in row.items()}

        geom = row_lower.get("_geometry")
        if not geom:
            lat = _safe_float(row_lower.get("lat") or row_lower.get("latitude"))
            lon = _safe_float(row_lower.get("lon") or row_lower.get("longitude"))
            if lat is not None and lon is not None:
                geom = {"type": "Point", "coordinates": [lon, lat]}
            else:
                continue  # skip rows with no geometry

        obs_id = str(
            row_lower.get("obs_id") or row_lower.get("id") or
            row_lower.get("observation_id") or f"GT{i:04d}"
        ).strip()

        raw_category = row_lower.get("category") or row_lower.get("type") or row_lower.get("feature_type")
        category = _normalise_category(raw_category)

        observed_value = str(
            row_lower.get("value") or row_lower.get("observed_value") or
            row_lower.get("land_use") or row_lower.get("description") or ""
        ).strip() or None

        conf_raw = row_lower.get("confidence") or row_lower.get("conf")
        confidence = _safe_float(conf_raw)
        if confidence is None:
            confidence = default_confidence
        confidence = max(0.0, min(1.0, confidence))

        obs_operator = str(
            row_lower.get("operator") or row_lower.get("surveyor") or
            row_lower.get("observer") or operator or ""
        ).strip() or None

        obs_date = str(
            row_lower.get("date") or row_lower.get("observation_date") or
            row_lower.get("survey_date") or ""
        ).strip() or None

        parcel_hint = str(
            row_lower.get("parcel") or row_lower.get("khasra_no") or
            row_lower.get("parcel_id") or row_lower.get("property_id") or ""
        ).strip() or None

        obs = GTObservation(
            obs_id=obs_id,
            geometry_geojson=geom,
            category=category,
            observed_value=observed_value,
            confidence=confidence,
            operator=obs_operator,
            observation_date=obs_date,
            notes=str(row_lower.get("notes", "")).strip() or None,
            linked_parcel_hint=parcel_hint,
            contradicts_source=str(row_lower.get("contradicts", "")).strip() or None,
            supports_source=str(row_lower.get("supports", "")).strip() or None,
            photo_reference=str(row_lower.get("photo", "") or row_lower.get("photo_ref", "")).strip() or None,
        )
        observations.append(obs)

    features = [_obs_to_feature(obs, prov_ds_id) for obs in observations]

    # Categorise what was found
    cat_summary: dict[str, int] = {}
    for obs in observations:
        cat_summary[obs.category] = cat_summary.get(obs.category, 0) + 1

    prov_nodes = [
        {
            "node_id": prov_origin_id,
            "node_type": "origin",
            "parent_ids": [],
            "label": f"Field ground truth survey ({operator or 'unknown operator'})",
        },
        {
            "node_id": prov_ds_id,
            "node_type": "dataset",
            "parent_ids": [prov_origin_id],
            "label": (
                f"GT observations ({len(observations)} records): "
                + ", ".join(f"{k}={v}" for k, v in sorted(cat_summary.items()))
            ),
        },
    ]

    return GTEvidence(
        observations=observations,
        features=features,
        provenance_nodes=prov_nodes,
        operator=operator,
        evidence_note=(
            f"Ground truth field survey: {len(observations)} observation(s). "
            f"Categories: {dict(cat_summary)}. "
            f"Quality weight: {GT_QUALITY_WEIGHT:.0%}. "
            "Field-verified observations provide an independent evidence lineage "
            "separate from any cadastral, revenue, or satellite source."
        ),
    )


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return None
