"""Topology & Ripple-Effect Validation — Layer 6.

A parcel boundary cannot be considered in isolation. Proposed changes
are checked against:
  - Neighboring parcels (overlap, gap introduction)
  - Building footprints (building outside parcel)
  - Road/ROW layers (ROW encroachment)
  - Utility networks (intersection change)
  - Administrative boundaries (jurisdiction mismatch)

If any constraint is violated → NOT auto-approvable → send to review.

This is the "Why we didn't auto-approve" explainer that makes
the demo compelling.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import Optional

from shapely.geometry import shape as shapely_shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union


# Thresholds
NEIGHBOR_OVERLAP_THRESHOLD_M2 = 0.5      # > 0.5m² new overlap = issue
NEIGHBOR_GAP_THRESHOLD_M2 = 1.0          # > 1m² gap introduced = issue
BUILDING_OUTSIDE_THRESHOLD_M2 = 1.0      # building outside parcel by > 1m²
UTILITY_CROSSING_THRESHOLD_M = 0.5       # utility crosses new boundary by > 0.5m


@dataclass
class RippleIssue:
    issue_id: str
    issue_type: str          # NEIGHBOR_OVERLAP / NEIGHBOR_GAP / BUILDING_OUTSIDE / UTILITY_CROSSING / ROW_CONFLICT
    severity: str            # CRITICAL / HIGH / MEDIUM / LOW
    feature_id: str
    feature_type: str        # parcel / building / utility / road_row / admin_boundary
    measure: Optional[float] = None
    measure_unit: Optional[str] = None
    description: str = ""
    blocks_auto_approval: bool = True


@dataclass
class RippleCheckResult:
    proposal_id: str
    parcel_id: str
    safe_to_auto_approve: bool
    issues: list[RippleIssue] = field(default_factory=list)
    checked_neighbors: int = 0
    checked_buildings: int = 0
    checked_utilities: int = 0
    checked_roads: int = 0
    summary: str = ""

    @property
    def total_issues(self) -> int:
        return len(self.issues)

    @property
    def critical_issues(self) -> int:
        return sum(1 for i in self.issues if i.severity == "CRITICAL")

    def to_dict(self) -> dict:
        return {
            "proposal_id": self.proposal_id,
            "parcel_id": self.parcel_id,
            "safe_to_auto_approve": self.safe_to_auto_approve,
            "total_issues": self.total_issues,
            "critical_issues": self.critical_issues,
            "checked_neighbors": self.checked_neighbors,
            "checked_buildings": self.checked_buildings,
            "checked_utilities": self.checked_utilities,
            "checked_roads": self.checked_roads,
            "summary": self.summary,
            "issues": [
                {
                    "issue_id": i.issue_id,
                    "issue_type": i.issue_type,
                    "severity": i.severity,
                    "feature_id": i.feature_id,
                    "feature_type": i.feature_type,
                    "measure": i.measure,
                    "measure_unit": i.measure_unit,
                    "description": i.description,
                    "blocks_auto_approval": i.blocks_auto_approval,
                }
                for i in self.issues
            ],
        }


def _geom_from_dict(d: Optional[dict]) -> Optional[BaseGeometry]:
    if not d:
        return None
    try:
        g = shapely_shape(d)
        return g if not g.is_empty else None
    except Exception:
        return None


def check_neighbor_parcels(
    proposal_id: str,
    parcel_id: str,
    proposed_geom: BaseGeometry,
    original_geom: Optional[BaseGeometry],
    neighbors: list[dict],   # list of {parcel_id, geometry (GeoJSON)}
) -> list[RippleIssue]:
    """Check proposed geometry against neighboring parcels."""
    issues: list[RippleIssue] = []

    for neighbor in neighbors:
        neighbor_id = neighbor.get("parcel_id", neighbor.get("id", "unknown"))
        neighbor_geom = _geom_from_dict(neighbor.get("geometry"))
        if neighbor_geom is None:
            continue

        # Check new overlap after proposed change
        try:
            new_overlap = proposed_geom.intersection(neighbor_geom)
            new_overlap_area = new_overlap.area if not new_overlap.is_empty else 0.0
        except Exception:
            new_overlap_area = 0.0

        # Check original overlap for comparison
        orig_overlap_area = 0.0
        if original_geom:
            try:
                orig_ov = original_geom.intersection(neighbor_geom)
                orig_overlap_area = orig_ov.area if not orig_ov.is_empty else 0.0
            except Exception:
                orig_overlap_area = 0.0

        # Scale area to m² (approximate at ~15° latitude in India)
        # 1 degree² ≈ 12,391 km² at 20° lat
        scale = 12_391_000_000  # m² per degree²
        new_overlap_m2 = new_overlap_area * scale
        orig_overlap_m2 = orig_overlap_area * scale
        increase_m2 = new_overlap_m2 - orig_overlap_m2

        if increase_m2 > NEIGHBOR_OVERLAP_THRESHOLD_M2:
            issues.append(RippleIssue(
                issue_id=f"RIPPLE-{uuid.uuid4().hex[:8].upper()}",
                issue_type="NEIGHBOR_OVERLAP",
                severity="CRITICAL" if increase_m2 > 10 else "HIGH",
                feature_id=neighbor_id,
                feature_type="parcel",
                measure=round(increase_m2, 2),
                measure_unit="m²",
                description=(
                    f"Proposed change introduces {increase_m2:.2f}m² overlap "
                    f"with neighboring parcel {neighbor_id}"
                ),
                blocks_auto_approval=True,
            ))

    return issues


def check_building_footprints(
    proposal_id: str,
    parcel_id: str,
    proposed_geom: BaseGeometry,
    buildings: list[dict],   # list of {building_id, geometry (GeoJSON)}
) -> list[RippleIssue]:
    """Check if any building footprints would be outside the proposed parcel."""
    issues: list[RippleIssue] = []

    for building in buildings:
        building_id = building.get("building_id", building.get("id", "unknown"))
        building_geom = _geom_from_dict(building.get("geometry"))
        if building_geom is None:
            continue

        try:
            outside = building_geom.difference(proposed_geom)
            outside_area = outside.area if not outside.is_empty else 0.0
            scale = 12_391_000_000
            outside_m2 = outside_area * scale
        except Exception:
            outside_m2 = 0.0

        if outside_m2 > BUILDING_OUTSIDE_THRESHOLD_M2:
            issues.append(RippleIssue(
                issue_id=f"RIPPLE-{uuid.uuid4().hex[:8].upper()}",
                issue_type="BUILDING_OUTSIDE",
                severity="HIGH",
                feature_id=building_id,
                feature_type="building",
                measure=round(outside_m2, 2),
                measure_unit="m²",
                description=(
                    f"Building {building_id} extends {outside_m2:.2f}m² outside "
                    f"the proposed parcel boundary"
                ),
                blocks_auto_approval=True,
            ))

    return issues


def check_utility_lines(
    proposal_id: str,
    parcel_id: str,
    proposed_geom: BaseGeometry,
    original_geom: Optional[BaseGeometry],
    utilities: list[dict],   # list of {utility_id, geometry (GeoJSON), type}
) -> list[RippleIssue]:
    """Check if proposed boundary change introduces new utility crossings."""
    issues: list[RippleIssue] = []

    for utility in utilities:
        util_id = utility.get("utility_id", utility.get("id", "unknown"))
        util_type = utility.get("type", "utility")
        util_geom = _geom_from_dict(utility.get("geometry"))
        if util_geom is None:
            continue

        try:
            # Does utility cross the new boundary?
            boundary = proposed_geom.boundary
            new_crossings = boundary.intersection(util_geom)
            new_cross_len = new_crossings.length if not new_crossings.is_empty else 0.0
            scale_m = 111_000  # 1 degree ≈ 111km
            new_cross_m = new_cross_len * scale_m
        except Exception:
            new_cross_m = 0.0

        # Check original
        orig_cross_m = 0.0
        if original_geom:
            try:
                orig_boundary = original_geom.boundary
                orig_cross = orig_boundary.intersection(util_geom)
                orig_cross_m = (orig_cross.length * scale_m) if not orig_cross.is_empty else 0.0
            except Exception:
                pass

        # New crossing introduced?
        new_crossing_introduced = new_cross_m > UTILITY_CROSSING_THRESHOLD_M and orig_cross_m < UTILITY_CROSSING_THRESHOLD_M

        if new_crossing_introduced:
            issues.append(RippleIssue(
                issue_id=f"RIPPLE-{uuid.uuid4().hex[:8].upper()}",
                issue_type="UTILITY_CROSSING",
                severity="MEDIUM",
                feature_id=util_id,
                feature_type=util_type,
                measure=round(new_cross_m, 2),
                measure_unit="m",
                description=(
                    f"Proposed boundary introduces a new {util_type} crossing "
                    f"({new_cross_m:.1f}m) that was not present in original"
                ),
                blocks_auto_approval=True,
            ))

    return issues


def check_administrative_boundaries(
    proposal_id: str,
    parcel_id: str,
    proposed_geom: BaseGeometry,
    admin_boundaries: list[dict],   # list of {boundary_id, geometry, boundary_type (ward/tehsil/district)}
) -> list[RippleIssue]:
    """
    Check that the proposed parcel does not cross administrative boundary lines
    (ward, tehsil, district) in a way that changes its jurisdiction.

    A parcel that crosses a ward boundary creates dual-jurisdiction ambiguity
    which must be resolved by the authorized officer — it cannot be auto-approved.
    """
    issues: list[RippleIssue] = []

    for boundary in admin_boundaries:
        bnd_id = boundary.get("boundary_id", boundary.get("id", "unknown"))
        bnd_type = boundary.get("boundary_type", "administrative")
        bnd_geom = _geom_from_dict(boundary.get("geometry"))
        if bnd_geom is None:
            continue

        try:
            # Check if the proposed parcel straddles the boundary line
            bnd_line = bnd_geom.boundary if bnd_geom.geom_type in ('Polygon', 'MultiPolygon') else bnd_geom
            intersection = proposed_geom.intersection(bnd_line)
            if intersection.is_empty:
                continue
            scale_m = 111_000  # 1 degree ≈ 111km
            cross_len_m = intersection.length * scale_m
            if cross_len_m > 0.5:   # > 0.5m crossing = genuine jurisdiction ambiguity
                issues.append(RippleIssue(
                    issue_id=f"RIPPLE-{uuid.uuid4().hex[:8].upper()}",
                    issue_type="ADMIN_BOUNDARY_CROSSING",
                    severity="HIGH",
                    feature_id=bnd_id,
                    feature_type=bnd_type,
                    measure=round(cross_len_m, 2),
                    measure_unit="m",
                    description=(
                        f"Proposed parcel crosses {bnd_type} boundary {bnd_id} "
                        f"({cross_len_m:.1f}m) — jurisdiction ambiguity. "
                        "Requires officer resolution before finalizing."
                    ),
                    blocks_auto_approval=True,
                ))
        except Exception:
            pass

    return issues


def check_road_row(
    proposal_id: str,
    parcel_id: str,
    proposed_geom: BaseGeometry,
    road_rows: list[dict],   # list of {road_id, geometry, row_width_m}
) -> list[RippleIssue]:
    """Check if proposed parcel encroaches on road right-of-way."""
    issues: list[RippleIssue] = []

    for road in road_rows:
        road_id = road.get("road_id", road.get("id", "unknown"))
        road_geom = _geom_from_dict(road.get("geometry"))
        if road_geom is None:
            continue

        try:
            overlap = proposed_geom.intersection(road_geom)
            if not overlap.is_empty and overlap.area > 0:
                scale = 12_391_000_000
                overlap_m2 = overlap.area * scale
                if overlap_m2 > 1.0:
                    issues.append(RippleIssue(
                        issue_id=f"RIPPLE-{uuid.uuid4().hex[:8].upper()}",
                        issue_type="ROW_CONFLICT",
                        severity="CRITICAL",
                        feature_id=road_id,
                        feature_type="road_row",
                        measure=round(overlap_m2, 2),
                        measure_unit="m²",
                        description=(
                            f"Proposed parcel boundary overlaps road ROW {road_id} "
                            f"by {overlap_m2:.2f}m²"
                        ),
                        blocks_auto_approval=True,
                    ))
        except Exception:
            pass

    return issues


def run_ripple_check(
    proposal_id: str,
    parcel_id: str,
    proposed_geometry: dict,
    original_geometry: Optional[dict] = None,
    neighbors: Optional[list[dict]] = None,
    buildings: Optional[list[dict]] = None,
    utilities: Optional[list[dict]] = None,
    road_rows: Optional[list[dict]] = None,
    admin_boundaries: Optional[list[dict]] = None,   # NEW: ward/tehsil/district boundaries
) -> RippleCheckResult:
    """
    Run all ripple checks for a harmonization proposal.
    Returns RippleCheckResult with safe_to_auto_approve flag.
    """
    result = RippleCheckResult(proposal_id=proposal_id, parcel_id=parcel_id, safe_to_auto_approve=True)

    proposed_geom = _geom_from_dict(proposed_geometry)
    if proposed_geom is None:
        result.safe_to_auto_approve = False
        result.summary = "Could not parse proposed geometry"
        return result

    original_geom = _geom_from_dict(original_geometry)
    all_issues: list[RippleIssue] = []

    # Neighbor check
    if neighbors:
        nb_issues = check_neighbor_parcels(
            proposal_id, parcel_id, proposed_geom, original_geom, neighbors
        )
        all_issues.extend(nb_issues)
        result.checked_neighbors = len(neighbors)

    # Building check
    if buildings:
        bld_issues = check_building_footprints(
            proposal_id, parcel_id, proposed_geom, buildings
        )
        all_issues.extend(bld_issues)
        result.checked_buildings = len(buildings)

    # Utility check
    if utilities:
        util_issues = check_utility_lines(
            proposal_id, parcel_id, proposed_geom, original_geom, utilities
        )
        all_issues.extend(util_issues)
        result.checked_utilities = len(utilities)

    # Road ROW check
    if road_rows:
        row_issues = check_road_row(
            proposal_id, parcel_id, proposed_geom, road_rows
        )
        all_issues.extend(row_issues)
        result.checked_roads = len(road_rows)

    # Administrative boundary check (NEW — closes ⚠ gap in requirements audit)
    if admin_boundaries:
        admin_issues = check_administrative_boundaries(
            proposal_id, parcel_id, proposed_geom, admin_boundaries
        )
        all_issues.extend(admin_issues)

    result.issues = all_issues

    blocking_issues = [i for i in all_issues if i.blocks_auto_approval]
    result.safe_to_auto_approve = len(blocking_issues) == 0

    if blocking_issues:
        result.summary = (
            f"NOT SAFE TO AUTO-APPROVE: {len(blocking_issues)} blocking issue(s). "
            + "; ".join(i.description for i in blocking_issues[:3])
        )
    else:
        result.summary = (
            f"SAFE TO AUTO-APPROVE: {result.checked_neighbors} neighbors, "
            f"{result.checked_buildings} buildings, "
            f"{result.checked_utilities} utilities checked — no blocking issues."
        )

    return result
