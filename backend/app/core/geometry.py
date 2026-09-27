"""Geometry validation, normalization, and comparison.

Implements: GeoJSON validation, CRS reprojection, IoU, Hausdorff,
area comparison, centroid distance, shape metrics.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Any, Optional

from shapely.geometry import shape as shapely_shape
from shapely.geometry.base import BaseGeometry
from shapely.validation import make_valid
from shapely.ops import transform
import pyproj
from pyproj import Transformer


SUPPORTED_GEOMETRY_TYPES = {
    "Point", "MultiPoint", "LineString", "MultiLineString",
    "Polygon", "MultiPolygon", "GeometryCollection",
}

# Conflict thresholds (configurable)
IOU_CONFLICT_THRESHOLD = 0.95       # IoU below this = potential conflict
HAUSDORFF_NOISE_M = 5.0             # below = measurement noise
HAUSDORFF_CONFLICT_M = 50.0         # above = definite conflict
AREA_RATIO_CONFLICT = 0.05          # >5% area difference = conflict


@dataclass
class GeometryValidationResult:
    valid: bool
    reason: str = ""
    geometry: Optional[BaseGeometry] = None


@dataclass
class GeometryComparisonResult:
    iou: float                          # -1 for non-polygon
    hausdorff_m: float
    area_ratio_diff: float              # abs(area_a - area_b) / max(area_a, area_b)
    centroid_dist_m: float
    conflict: bool
    conflict_type: str                  # NONE / AREA_MISMATCH / BOUNDARY_OFFSET / OVERLAP / GAP
    reason: str
    measurements: dict = field(default_factory=dict)


def validate_geojson_geometry(geom_dict: Any) -> GeometryValidationResult:
    """Validate a GeoJSON geometry dict. Returns repaired geometry on success."""
    if not isinstance(geom_dict, dict):
        return GeometryValidationResult(False, "geometry must be a JSON object")
    gtype = geom_dict.get("type")
    if gtype not in SUPPORTED_GEOMETRY_TYPES:
        return GeometryValidationResult(False, f"unsupported geometry type: {gtype!r}")
    if gtype != "GeometryCollection":
        if geom_dict.get("coordinates") is None:
            return GeometryValidationResult(False, "missing coordinates")
    else:
        if not geom_dict.get("geometries"):
            return GeometryValidationResult(False, "empty GeometryCollection")
    try:
        geom = shapely_shape(geom_dict)
    except Exception as e:
        return GeometryValidationResult(False, f"shapely parse error: {e}")
    if geom.is_empty:
        return GeometryValidationResult(False, "empty geometry")
    if not geom.is_valid:
        fixed = make_valid(geom)
        if fixed.is_empty:
            return GeometryValidationResult(False, "invalid and unfixable geometry")
        geom = fixed
    return GeometryValidationResult(True, "valid", geom)


def normalize_to_wgs84(geom: BaseGeometry, source_crs: str = "EPSG:4326") -> BaseGeometry:
    """Reproject geometry to WGS84. No-op if already EPSG:4326."""
    normalized = source_crs.upper().replace(" ", "")
    if normalized in ("EPSG:4326", "WGS84", "CRS:84", "URN:OGC:DEF:CRS:EPSG::4326"):
        return geom
    transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
    return transform(transformer.transform, geom)


def _metres_per_degree_at_lat(lat: float) -> tuple[float, float]:
    """Approximate metres-per-degree at given latitude (WGS84 ellipsoid)."""
    lat_rad = math.radians(lat)
    m_per_deg_lat = 111132.92 - 559.82 * math.cos(2 * lat_rad) + 1.175 * math.cos(4 * lat_rad)
    m_per_deg_lon = 111412.84 * math.cos(lat_rad) - 93.5 * math.cos(3 * lat_rad)
    return m_per_deg_lat, m_per_deg_lon


def _midpoint_scale(geom_a: BaseGeometry, geom_b: BaseGeometry) -> float:
    """Average metres-per-degree at midpoint latitude of two geometries."""
    mid_lat = (geom_a.centroid.y + geom_b.centroid.y) / 2.0
    m_lat, m_lon = _metres_per_degree_at_lat(mid_lat)
    return (m_lat + m_lon) / 2.0


def compute_iou(geom_a: BaseGeometry, geom_b: BaseGeometry) -> float:
    """Intersection-over-Union for polygon types. Returns -1 for non-polygons."""
    if geom_a.geom_type not in ("Polygon", "MultiPolygon") or \
       geom_b.geom_type not in ("Polygon", "MultiPolygon"):
        return -1.0
    try:
        inter = geom_a.intersection(geom_b).area
        union = geom_a.union(geom_b).area
        if union == 0:
            return 1.0 if inter == 0 else 0.0
        return inter / union
    except Exception:
        return 0.0


def compute_hausdorff_metres(geom_a: BaseGeometry, geom_b: BaseGeometry) -> float:
    """Hausdorff distance in metres using midpoint latitude scale."""
    try:
        hd_deg = geom_a.hausdorff_distance(geom_b)
        scale = _midpoint_scale(geom_a, geom_b)
        return hd_deg * scale
    except Exception:
        return float("inf")


def compute_centroid_dist_metres(geom_a: BaseGeometry, geom_b: BaseGeometry) -> float:
    """Centroid-to-centroid distance in metres."""
    try:
        cx_a, cy_a = geom_a.centroid.x, geom_a.centroid.y
        cx_b, cy_b = geom_b.centroid.x, geom_b.centroid.y
        dx = (cx_a - cx_b)
        dy = (cy_a - cy_b)
        mid_lat = (cy_a + cy_b) / 2.0
        m_lat, m_lon = _metres_per_degree_at_lat(mid_lat)
        return math.sqrt((dx * m_lon) ** 2 + (dy * m_lat) ** 2)
    except Exception:
        return float("inf")


def compute_area_ratio_diff(geom_a: BaseGeometry, geom_b: BaseGeometry) -> float:
    """Relative area difference: |area_a - area_b| / max(area_a, area_b)."""
    try:
        a_a = geom_a.area
        a_b = geom_b.area
        denom = max(a_a, a_b)
        if denom == 0:
            return 0.0
        return abs(a_a - a_b) / denom
    except Exception:
        return 0.0


def area_sqm(geom: BaseGeometry) -> float:
    """Approximate area in square metres at centroid latitude."""
    try:
        lat = geom.centroid.y
        m_lat, m_lon = _metres_per_degree_at_lat(lat)
        scale = m_lat * m_lon
        # area in degrees² → m²  (rough, adequate for parcel sizes)
        return geom.area * scale
    except Exception:
        return 0.0


def compare_geometries(
    geom_a: BaseGeometry,
    geom_b: BaseGeometry,
    iou_threshold: float = IOU_CONFLICT_THRESHOLD,
    hausdorff_noise_m: float = HAUSDORFF_NOISE_M,
    hausdorff_conflict_m: float = HAUSDORFF_CONFLICT_M,
    area_ratio_threshold: float = AREA_RATIO_CONFLICT,
) -> GeometryComparisonResult:
    """Full geometry comparison for two WGS84 geometries."""
    iou = compute_iou(geom_a, geom_b)
    hausdorff_m = compute_hausdorff_metres(geom_a, geom_b)
    area_diff = compute_area_ratio_diff(geom_a, geom_b)
    centroid_m = compute_centroid_dist_metres(geom_a, geom_b)

    measurements = {
        "iou": round(iou, 6) if iou >= 0 else None,
        "hausdorff_m": round(hausdorff_m, 3) if hausdorff_m != float("inf") else None,
        "area_ratio_diff": round(area_diff, 6),
        "centroid_dist_m": round(centroid_m, 3) if centroid_m != float("inf") else None,
        "area_a_sqm": round(area_sqm(geom_a), 2),
        "area_b_sqm": round(area_sqm(geom_b), 2),
    }

    # Non-polygon: use Hausdorff only
    if iou < 0:
        if hausdorff_m <= hausdorff_noise_m:
            return GeometryComparisonResult(iou, hausdorff_m, area_diff, centroid_m,
                                            False, "NONE", "within noise tolerance", measurements)
        conflict = hausdorff_m >= hausdorff_conflict_m
        ctype = "BOUNDARY_OFFSET" if conflict else "NONE"
        return GeometryComparisonResult(iou, hausdorff_m, area_diff, centroid_m,
                                        conflict, ctype,
                                        f"Non-polygon Hausdorff={hausdorff_m:.1f}m", measurements)

    # Polygon checks
    iou_conflict = iou < iou_threshold
    hd_conflict = hausdorff_m >= hausdorff_conflict_m
    area_conflict = area_diff > area_ratio_threshold
    noise = hausdorff_m < hausdorff_noise_m

    if noise and not iou_conflict and not area_conflict:
        return GeometryComparisonResult(iou, hausdorff_m, area_diff, centroid_m,
                                        False, "NONE", "within noise tolerance", measurements)

    # Determine primary conflict type
    conflict_type = "NONE"
    if iou_conflict and hd_conflict:
        # Check for actual overlap vs offset
        try:
            overlap_area = geom_a.intersection(geom_b).area
            if overlap_area < 0.01 * min(geom_a.area, geom_b.area):
                conflict_type = "GAP"
            elif iou < 0.5:
                conflict_type = "BOUNDARY_OFFSET"
            else:
                conflict_type = "OVERLAP"
        except Exception:
            conflict_type = "BOUNDARY_OFFSET"
    elif iou_conflict:
        conflict_type = "BOUNDARY_OFFSET"
    elif hd_conflict:
        conflict_type = "BOUNDARY_OFFSET"
    elif area_conflict:
        conflict_type = "AREA_MISMATCH"

    is_conflict = iou_conflict or hd_conflict or area_conflict
    reason = (
        f"IoU={iou:.3f} Hausdorff={hausdorff_m:.1f}m area_diff={area_diff:.1%}"
        if is_conflict
        else "no significant geometric difference"
    )
    return GeometryComparisonResult(iou, hausdorff_m, area_diff, centroid_m,
                                    is_conflict, conflict_type, reason, measurements)
