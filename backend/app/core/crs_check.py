"""CRS and coordinate plausibility checking.

Four-gate pipeline (most specific first):
  1. Impossible geographic extents (>90° lat / >180° lon)
  2. Degree/metre confusion (values >> 360)
  3. Axis-order suspicion (India-aware lat/lon swap)
  4. Plausibility warning (outside India ±10°)

A transformation record is appended whenever reprojection occurs —
never silently transform without recording the operation.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from shapely.geometry.base import BaseGeometry


@dataclass
class CRSCheckResult:
    ok: bool
    issue: str                  # "" if ok
    category: str               # NONE / IMPOSSIBLE_EXTENT / DEGREE_METRE_CONFUSION / AXIS_ORDER / PLAUSIBILITY
    declared_crs: str = "EPSG:4326"


@dataclass
class CRSTransformRecord:
    """Immutable record of a CRS transformation operation."""
    source_crs: str
    target_crs: str = "EPSG:4326"
    method: str = "pyproj/PROJ"
    accuracy_note: str = "datum-aware via PROJ transformation grid"
    timestamp_utc: str = ""


# India bounding box (WGS84)
INDIA_LON_MIN, INDIA_LON_MAX = 67.0, 98.0
INDIA_LAT_MIN, INDIA_LAT_MAX = 6.0, 38.0

# Projected metre indicator
METRE_RANGE_THRESHOLD = 1000.0


def check_crs_plausibility(
    geom: BaseGeometry,
    declared_crs: str = "EPSG:4326",
) -> CRSCheckResult:
    """Check if geometry coordinates are plausible for the declared CRS."""
    if declared_crs not in ("EPSG:4326", "WGS84", "CRS:84",
                             "urn:ogc:def:crs:EPSG::4326"):
        return CRSCheckResult(True, "", "NONE", declared_crs)

    minx, miny, maxx, maxy = geom.bounds

    # Gate 1: Impossible extents
    if abs(miny) > 90 or abs(maxy) > 90:
        return CRSCheckResult(
            False,
            f"latitude outside [-90,90]: min={miny:.3f} max={maxy:.3f}",
            "IMPOSSIBLE_EXTENT", declared_crs,
        )
    if abs(minx) > 180 or abs(maxx) > 180:
        return CRSCheckResult(
            False,
            f"longitude outside [-180,180]: min={minx:.3f} max={maxx:.3f}",
            "IMPOSSIBLE_EXTENT", declared_crs,
        )

    # Gate 2: Degree/metre confusion
    max_val = max(abs(minx), abs(maxx), abs(miny), abs(maxy))
    if max_val > METRE_RANGE_THRESHOLD:
        return CRSCheckResult(
            False,
            f"values >> 360 suggest projected metres mislabeled as degrees: "
            f"lon=[{minx:.0f},{maxx:.0f}] lat=[{miny:.0f},{maxy:.0f}]",
            "DEGREE_METRE_CONFUSION", declared_crs,
        )

    # Gate 3: Axis-order (India-context)
    x_in_lat = INDIA_LAT_MIN <= minx <= INDIA_LAT_MAX and INDIA_LAT_MIN <= maxx <= INDIA_LAT_MAX
    y_in_lon = INDIA_LON_MIN <= miny <= INDIA_LON_MAX and INDIA_LON_MIN <= maxy <= INDIA_LON_MAX
    if x_in_lat and y_in_lon:
        return CRSCheckResult(
            False,
            f"lat/lon axis swap suspected: x={minx:.2f}-{maxx:.2f} (looks like lat), "
            f"y={miny:.2f}-{maxy:.2f} (looks like Indian lon)",
            "AXIS_ORDER", declared_crs,
        )

    # Gate 4: Plausibility warning (not a hard failure)
    if not (INDIA_LON_MIN - 10 <= minx and maxx <= INDIA_LON_MAX + 10
            and INDIA_LAT_MIN - 10 <= miny and maxy <= INDIA_LAT_MAX + 10):
        return CRSCheckResult(
            True,   # warning only
            f"coordinates outside India ±10°: lon=[{minx:.2f},{maxx:.2f}] lat=[{miny:.2f},{maxy:.2f}]",
            "PLAUSIBILITY", declared_crs,
        )

    return CRSCheckResult(True, "", "NONE", declared_crs)
