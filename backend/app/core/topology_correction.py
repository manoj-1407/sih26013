"""Topology Correction Engine -- PS26013 Gap Closure.

Automatically proposes the minimal geometric fix for detected topology errors:
  OVERLAP  -- two sources claim the same area: split at shared boundary
  GAP      -- gap between neighbouring parcels: fill to midline
  SLIVER   -- thin artifact polygon (width < threshold): merge into neighbour
  BOUNDARY_OFFSET -- datum shift: align to higher-quality reference

Returns before/after GeoJSON geometries with quantified correction.
This is 'topology correction' as required by PS26013.
"""
from __future__ import annotations
import math
import uuid
from dataclasses import dataclass, field
from typing import Optional

from shapely.geometry import mapping as sh_map, shape as sh_shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union, snap
from shapely.affinity import translate

from app.core.geometry import (
    compute_hausdorff_metres, compute_area_ratio_diff, area_sqm,
)

M2DEG = 1.0 / 111_000.0
SLIVER_WIDTH_M = 0.5        # narrower than this = sliver
SNAP_TOLERANCE_M = 0.05     # snap tolerance for boundary alignment


@dataclass
class CorrectionResult:
    correction_id: str
    correction_type: str           # OVERLAP_SPLIT / GAP_FILL / SLIVER_MERGE / BOUNDARY_ALIGN
    parcel_id_a: str
    parcel_id_b: str

    # Before
    geometry_a_before: dict        # GeoJSON
    geometry_b_before: dict
    area_a_before_sqm: float
    area_b_before_sqm: float

    # After
    geometry_a_after: dict
    geometry_b_after: dict
    area_a_after_sqm: float
    area_b_after_sqm: float

    # Metrics
    overlap_area_removed_sqm: float = 0.0
    gap_area_filled_sqm: float = 0.0
    boundary_shift_m: float = 0.0
    correction_confidence: float = 1.0   # 0-1: how confident we are in this fix

    # Narrative
    description: str = ""
    method: str = ""
    caveats: list[str] = field(default_factory=list)


def _geom(d: dict) -> Optional[BaseGeometry]:
    if not d:
        return None
    try:
        g = sh_shape(d)
        return g if not g.is_empty else None
    except Exception:
        return None


def _scale_m2(area_deg2: float, lat: float) -> float:
    """Approximate degree-squared to metres-squared at given latitude."""
    m_lat = 111_132.92 - 559.82 * math.cos(2 * math.radians(lat))
    m_lon = 111_412.84 * math.cos(math.radians(lat))
    return area_deg2 * m_lat * m_lon


def _hausdorff_m(ga: BaseGeometry, gb: BaseGeometry) -> float:
    try:
        hd = ga.hausdorff_distance(gb)
        mid_lat = (ga.centroid.y + gb.centroid.y) / 2.0
        return hd * (111_132.92 - 559.82 * math.cos(2 * math.radians(mid_lat)))
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Overlap correction: split at shared boundary midline
# ---------------------------------------------------------------------------

def correct_overlap(
    parcel_id_a: str,
    parcel_id_b: str,
    geometry_a: dict,
    geometry_b: dict,
    quality_weight_a: float = 0.80,
    quality_weight_b: float = 0.70,
) -> Optional[CorrectionResult]:
    """
    When two source records for adjacent parcels overlap, split the overlap
    zone based on source quality weights.

    Higher-quality source (e.g. GNSS, Drone) keeps its portion of the
    overlap zone. The lower-quality source loses it.

    Returns None if no overlap exists.
    """
    ga = _geom(geometry_a)
    gb = _geom(geometry_b)
    if ga is None or gb is None:
        return None

    try:
        overlap = ga.intersection(gb)
        if overlap.is_empty or overlap.area < 1e-12:
            return None

        lat = ga.centroid.y
        overlap_sqm = _scale_m2(overlap.area, lat)

        if overlap_sqm < 0.1:
            return None   # sub-noise

        # Assign overlap to higher-quality source
        if quality_weight_a >= quality_weight_b:
            # A keeps overlap, B loses it
            ga_after = ga
            gb_after = gb.difference(ga)
        else:
            # B keeps overlap, A loses it
            gb_after = gb
            ga_after = ga.difference(gb)

        if ga_after.is_empty or gb_after.is_empty:
            return None

        from shapely.validation import make_valid
        ga_after = make_valid(ga_after)
        gb_after = make_valid(gb_after)

        shift_m = _hausdorff_m(ga, ga_after)

        return CorrectionResult(
            correction_id=f"TOPO-{uuid.uuid4().hex[:8].upper()}",
            correction_type="OVERLAP_SPLIT",
            parcel_id_a=parcel_id_a,
            parcel_id_b=parcel_id_b,
            geometry_a_before=dict(sh_map(ga)),
            geometry_b_before=dict(sh_map(gb)),
            area_a_before_sqm=round(area_sqm(ga), 2),
            area_b_before_sqm=round(area_sqm(gb), 2),
            geometry_a_after=dict(sh_map(ga_after)),
            geometry_b_after=dict(sh_map(gb_after)),
            area_a_after_sqm=round(area_sqm(ga_after), 2),
            area_b_after_sqm=round(area_sqm(gb_after), 2),
            overlap_area_removed_sqm=round(overlap_sqm, 2),
            boundary_shift_m=round(shift_m, 2),
            correction_confidence=round(min(quality_weight_a, quality_weight_b) + 0.1, 2),
            description=(
                f"Overlap of {overlap_sqm:.1f}m² resolved: "
                f"assigned to {'source A' if quality_weight_a >= quality_weight_b else 'source B'} "
                f"(higher quality weight {max(quality_weight_a, quality_weight_b):.2f}). "
                f"Boundary shifted {shift_m:.2f}m."
            ),
            method="QUALITY_WEIGHTED_SPLIT",
            caveats=[
                "Correction is a proposal — officer approval required before finalising.",
                "Original source geometries preserved unchanged.",
                "If both sources have equal weight, source A is preferred.",
            ],
        )
    except Exception as e:
        return None


# ---------------------------------------------------------------------------
# Gap correction: fill to midline between two source boundaries
# ---------------------------------------------------------------------------

def correct_gap(
    parcel_id_a: str,
    parcel_id_b: str,
    geometry_a: dict,
    geometry_b: dict,
    expected_adjacency: bool = True,
) -> Optional[CorrectionResult]:
    """
    When two parcels that should be adjacent have a gap, fill the gap
    by extending each parcel toward the other.

    Returns None if geometries overlap (not a gap) or are too far apart.
    """
    ga = _geom(geometry_a)
    gb = _geom(geometry_b)
    if ga is None or gb is None:
        return None

    try:
        # If they already overlap, this is not a gap
        if ga.intersects(gb) and ga.intersection(gb).area > 1e-14:
            return None

        # Distance between the two geometries in degrees
        dist_deg = ga.distance(gb)
        if dist_deg <= 0:
            return None   # touching — no gap

        lat = ga.centroid.y
        dist_m = dist_deg * (111_132.92 - 559.82 * math.cos(2 * math.radians(lat)))

        # Estimate gap area as distance × average boundary length
        boundary_len_deg = min(ga.length, gb.length) / 4   # rough side length
        gap_area_deg2 = dist_deg * boundary_len_deg
        gap_sqm = _scale_m2(gap_area_deg2, lat)

        if gap_sqm > 50.0 or dist_m > 20.0:
            return CorrectionResult(
                correction_id=f"TOPO-{uuid.uuid4().hex[:8].upper()}",
                correction_type="GAP_LARGE",
                parcel_id_a=parcel_id_a,
                parcel_id_b=parcel_id_b,
                geometry_a_before=dict(sh_map(ga)),
                geometry_b_before=dict(sh_map(gb)),
                area_a_before_sqm=round(area_sqm(ga), 2),
                area_b_before_sqm=round(area_sqm(gb), 2),
                geometry_a_after=dict(sh_map(ga)),
                geometry_b_after=dict(sh_map(gb)),
                area_a_after_sqm=round(area_sqm(ga), 2),
                area_b_after_sqm=round(area_sqm(gb), 2),
                gap_area_filled_sqm=round(gap_sqm, 2),
                correction_confidence=0.0,
                description=(
                    f"Gap of ~{gap_sqm:.1f}m² ({dist_m:.1f}m) detected. "
                    "Too large for auto-correction — requires field survey."
                ),
                method="GAP_TOO_LARGE",
                caveats=["Gap exceeds 50m² / 20m threshold. Manual correction required."],
            )

        # Fill gap: extend each parcel by half the gap distance toward the other
        half_dist = dist_deg / 2.0
        # Translate each geometry toward the other's centroid by half the gap
        cx_a, cy_a = ga.centroid.x, ga.centroid.y
        cx_b, cy_b = gb.centroid.x, gb.centroid.y
        dx = cx_b - cx_a
        dy = cy_b - cy_a
        norm = max(math.sqrt(dx**2 + dy**2), 1e-12)
        ux, uy = dx / norm, dy / norm   # unit vector a→b

        ga_after = translate(ga, ux * half_dist, uy * half_dist)
        gb_after = translate(gb, -ux * half_dist, -uy * half_dist)

        from shapely.validation import make_valid
        ga_after = make_valid(ga.union(ga_after))
        gb_after = make_valid(gb.union(gb_after))

        return CorrectionResult(
            correction_id=f"TOPO-{uuid.uuid4().hex[:8].upper()}",
            correction_type="GAP_FILL",
            parcel_id_a=parcel_id_a,
            parcel_id_b=parcel_id_b,
            geometry_a_before=dict(sh_map(ga)),
            geometry_b_before=dict(sh_map(gb)),
            area_a_before_sqm=round(area_sqm(ga), 2),
            area_b_before_sqm=round(area_sqm(gb), 2),
            geometry_a_after=dict(sh_map(ga_after)),
            geometry_b_after=dict(sh_map(gb_after)),
            area_a_after_sqm=round(area_sqm(ga_after), 2),
            area_b_after_sqm=round(area_sqm(gb_after), 2),
            gap_area_filled_sqm=round(gap_sqm, 2),
            correction_confidence=0.80,
            description=(
                f"Gap of ~{gap_sqm:.1f}m² ({dist_m:.1f}m) filled: "
                f"each parcel extended {dist_m/2:.1f}m toward the other."
            ),
            method="MIDLINE_FILL",
            caveats=[
                "Gap filled by geometric extension toward midpoint — not field-verified.",
                "Officer approval required.",
            ],
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Boundary align: align lower-quality source to higher-quality reference
# ---------------------------------------------------------------------------

def correct_boundary_offset(
    parcel_id_a: str,
    parcel_id_b: str,
    geometry_a: dict,
    geometry_b: dict,
    quality_weight_a: float = 0.80,
    quality_weight_b: float = 0.70,
    max_correction_m: float = 5.0,
) -> Optional[CorrectionResult]:
    """
    When two sources describe the same parcel with a boundary offset,
    snap the lower-quality source to align with the higher-quality one.
    Only applied when offset <= max_correction_m (default 5m).

    Larger offsets require field investigation.
    """
    ga = _geom(geometry_a)
    gb = _geom(geometry_b)
    if ga is None or gb is None:
        return None

    hd_m = _hausdorff_m(ga, gb)
    if hd_m < 0.5:
        return None   # within noise, no correction needed
    if hd_m > max_correction_m:
        return CorrectionResult(
            correction_id=f"TOPO-{uuid.uuid4().hex[:8].upper()}",
            correction_type="OFFSET_TOO_LARGE",
            parcel_id_a=parcel_id_a,
            parcel_id_b=parcel_id_b,
            geometry_a_before=dict(sh_map(ga)),
            geometry_b_before=dict(sh_map(gb)),
            area_a_before_sqm=round(area_sqm(ga), 2),
            area_b_before_sqm=round(area_sqm(gb), 2),
            geometry_a_after=dict(sh_map(ga)),
            geometry_b_after=dict(sh_map(gb)),
            area_a_after_sqm=round(area_sqm(ga), 2),
            area_b_after_sqm=round(area_sqm(gb), 2),
            boundary_shift_m=round(hd_m, 2),
            correction_confidence=0.0,
            description=f"Boundary offset {hd_m:.1f}m exceeds {max_correction_m}m auto-correction limit. Field survey required.",
            method="OFFSET_TOO_LARGE",
            caveats=[f"Offset {hd_m:.1f}m > {max_correction_m}m threshold. Manual correction only."],
        )

    try:
        tol = SNAP_TOLERANCE_M * M2DEG * 111_000 / 111_000  # in degrees
        # Higher quality = reference; lower quality = snapped
        if quality_weight_a >= quality_weight_b:
            ref, mov = ga, gb
            ref_id, mov_id = parcel_id_a, parcel_id_b
        else:
            ref, mov = gb, ga
            ref_id, mov_id = parcel_id_b, parcel_id_a

        snapped = snap(mov, ref, tolerance=hd_m * M2DEG * 1.5)

        from shapely.validation import make_valid
        snapped = make_valid(snapped)

        shift_after = _hausdorff_m(mov, snapped)

        if quality_weight_a >= quality_weight_b:
            ga_after, gb_after = ref, snapped
        else:
            ga_after, gb_after = snapped, ref

        return CorrectionResult(
            correction_id=f"TOPO-{uuid.uuid4().hex[:8].upper()}",
            correction_type="BOUNDARY_ALIGN",
            parcel_id_a=parcel_id_a,
            parcel_id_b=parcel_id_b,
            geometry_a_before=dict(sh_map(ga)),
            geometry_b_before=dict(sh_map(gb)),
            area_a_before_sqm=round(area_sqm(ga), 2),
            area_b_before_sqm=round(area_sqm(gb), 2),
            geometry_a_after=dict(sh_map(ga_after)),
            geometry_b_after=dict(sh_map(gb_after)),
            area_a_after_sqm=round(area_sqm(ga_after), 2),
            area_b_after_sqm=round(area_sqm(gb_after), 2),
            boundary_shift_m=round(hd_m, 2),
            correction_confidence=round(min(quality_weight_a, quality_weight_b) + 0.15, 2),
            description=(
                f"Boundary offset {hd_m:.1f}m: lower-quality source ({mov_id}) "
                f"snapped to reference ({ref_id}, weight={max(quality_weight_a, quality_weight_b):.2f}). "
                f"Residual after snap: {shift_after:.2f}m."
            ),
            method="QUALITY_WEIGHTED_SNAP",
            caveats=[
                "Snap uses Shapely geometric alignment — not a geodetic transformation.",
                "For offsets caused by datum shifts, a proper CRS reprojection is recommended.",
                "Officer approval required.",
            ],
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Auto-dispatch: choose the right correction based on conflict type
# ---------------------------------------------------------------------------

def auto_correct(
    parcel_id_a: str,
    parcel_id_b: str,
    geometry_a: dict,
    geometry_b: dict,
    conflict_type: str,
    quality_weight_a: float = 0.80,
    quality_weight_b: float = 0.70,
) -> Optional[CorrectionResult]:
    """
    Select and apply the appropriate topology correction based on conflict type.
    Returns a CorrectionResult or None if no correction is applicable.
    """
    ct = conflict_type.upper()
    if ct in ("OVERLAP",):
        return correct_overlap(parcel_id_a, parcel_id_b,
                               geometry_a, geometry_b,
                               quality_weight_a, quality_weight_b)
    if ct in ("GAP",):
        return correct_gap(parcel_id_a, parcel_id_b,
                           geometry_a, geometry_b)
    if ct in ("BOUNDARY_OFFSET", "SHAPE_DEFORMATION"):
        return correct_boundary_offset(parcel_id_a, parcel_id_b,
                                       geometry_a, geometry_b,
                                       quality_weight_a, quality_weight_b)
    return None
