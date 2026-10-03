"""DSM/DTM Elevation Adapter — PS26013 Gap Closure.

Integrates Digital Surface Model (DSM) and Digital Terrain Model (DTM)
data into the GeoSamanvay reconciliation pipeline.

WHAT WE DO:
  - Extract spatial extent, CRS, resolution from GeoTIFF rasters
  - Accept pre-extracted elevation statistics per parcel (from external tools)
  - Compute building height estimates: building_height = DSM_mean - DTM_mean
  - Feed elevation evidence into the provenance graph and matching engine
  - Flag elevation conflicts (e.g. DSM shows building but cadastral says vacant)

WHAT WE DON'T DO:
  - Raw pixel processing / photogrammetry (that's upstream of us)
  - Terrain analysis or slope/aspect computation
  - We consume elevation data, we don't generate it

Architecture:
  DSM/DTM raster (GeoTIFF)  OR  pre-extracted elevation stats (CSV/JSON)
          ↓
    ElevationAdapter
          ↓
    Canonical features with elevation evidence
          ↓
    Standard ingestor pipeline (SourceType.DSM_DTM)
          ↓
    Matching / conflict / provenance engines
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import uuid


# ─────────────────────────────────────────────────────────────────────────────
# Quality weights for elevation sources
# ─────────────────────────────────────────────────────────────────────────────

ELEVATION_QUALITY_WEIGHTS = {
    "lidar": 1.00,           # LiDAR — highest accuracy
    "drone_photogrammetry": 0.92,  # UAV/drone photogrammetry < 5cm GSD
    "satellite_stereo": 0.80,      # Stereo satellite (Cartosat, etc.)
    "contour_interpolated": 0.60,  # Interpolated from contour maps
    "srtm": 0.55,            # SRTM 30m — coarse, old
    "aster_gdem": 0.50,
    "unknown": 0.50,
}


@dataclass
class ElevationParcelStats:
    """Elevation statistics for a single parcel, pre-extracted from DSM/DTM."""
    parcel_id_hint: Optional[str]   # Khasra/property ID to link to source records
    geometry_geojson: Optional[dict]  # Parcel polygon over which stats are computed
    dsm_mean_m: Optional[float]     # Mean DSM value (includes buildings)
    dsm_min_m: Optional[float]
    dsm_max_m: Optional[float]
    dtm_mean_m: Optional[float]     # Mean DTM value (bare earth)
    dtm_min_m: Optional[float]
    dtm_max_m: Optional[float]
    estimated_building_height_m: Optional[float]  # dsm_mean - dtm_mean
    has_structure: bool             # True if building_height > threshold
    pixel_count: Optional[int]
    resolution_m: Optional[float]   # Ground pixel resolution in metres
    source_type: str = "unknown"    # lidar / drone_photogrammetry / satellite_stereo / etc.
    acquisition_date: Optional[str] = None
    crs: str = "EPSG:4326"


@dataclass
class ElevationEvidence:
    """Evidence derived from elevation data for a parcel group."""
    parcel_stats: list[ElevationParcelStats]
    source_type: str
    quality_weight: float
    provenance_nodes: list[dict]
    features: list[dict]           # canonical feature dicts for ingestor
    evidence_note: str


BUILDING_HEIGHT_THRESHOLD_M = 1.5  # DSM - DTM > 1.5m → structure present


def _compute_building_height(
    dsm_mean: Optional[float],
    dtm_mean: Optional[float],
) -> Optional[float]:
    if dsm_mean is None or dtm_mean is None:
        return None
    return round(dsm_mean - dtm_mean, 2)


def adapt_elevation_stats(
    stats_records: list[dict],
    source_type: str = "unknown",
    acquisition_date: Optional[str] = None,
) -> ElevationEvidence:
    """
    Adapt pre-extracted elevation statistics into canonical features.

    Each record in stats_records should have at minimum:
      - geometry: GeoJSON polygon of the area measured
      - dsm_mean_m (float): mean DSM value in metres
      - dtm_mean_m (float): mean DTM value in metres

    Optional fields:
      - parcel_id, khasra_no (links to source records)
      - dsm_min_m, dsm_max_m, dtm_min_m, dtm_max_m
      - pixel_count, resolution_m
      - acquisition_date

    Returns ElevationEvidence with canonical features ready for ingestor.
    """
    quality_weight = ELEVATION_QUALITY_WEIGHTS.get(source_type.lower(), 0.50)
    prov_origin_id = f"ORIG-ELEV-{uuid.uuid4().hex[:8].upper()}"
    prov_ds_id = f"DS-ELEV-{uuid.uuid4().hex[:8].upper()}"

    features = []
    parcel_stats_list = []

    for rec in stats_records:
        geom = rec.get("geometry")
        dsm_mean = _safe_float(rec.get("dsm_mean_m") or rec.get("dsm_mean"))
        dtm_mean = _safe_float(rec.get("dtm_mean_m") or rec.get("dtm_mean"))
        dsm_min  = _safe_float(rec.get("dsm_min_m") or rec.get("dsm_min"))
        dsm_max  = _safe_float(rec.get("dsm_max_m") or rec.get("dsm_max"))
        dtm_min  = _safe_float(rec.get("dtm_min_m") or rec.get("dtm_min"))
        dtm_max  = _safe_float(rec.get("dtm_max_m") or rec.get("dtm_max"))
        res_m    = _safe_float(rec.get("resolution_m") or rec.get("gsd_m"))
        pix_cnt  = rec.get("pixel_count")
        acq_date = rec.get("acquisition_date") or acquisition_date
        parcel_hint = (
            str(rec.get("parcel_id") or rec.get("khasra_no") or rec.get("property_id") or "")
        ).strip() or None

        bldg_height = _compute_building_height(dsm_mean, dtm_mean)
        has_structure = (bldg_height is not None and bldg_height > BUILDING_HEIGHT_THRESHOLD_M)

        stats = ElevationParcelStats(
            parcel_id_hint=parcel_hint,
            geometry_geojson=geom,
            dsm_mean_m=dsm_mean,
            dsm_min_m=dsm_min,
            dsm_max_m=dsm_max,
            dtm_mean_m=dtm_mean,
            dtm_min_m=dtm_min,
            dtm_max_m=dtm_max,
            estimated_building_height_m=bldg_height,
            has_structure=has_structure,
            pixel_count=int(pix_cnt) if pix_cnt is not None else None,
            resolution_m=res_m,
            source_type=source_type,
            acquisition_date=str(acq_date) if acq_date else None,
        )
        parcel_stats_list.append(stats)

        # Build canonical feature for ingestor
        props = {
            "parcel_reference": parcel_hint,
            "source_elevation_type": source_type,
            "dsm_mean_m": dsm_mean,
            "dsm_min_m": dsm_min,
            "dsm_max_m": dsm_max,
            "dtm_mean_m": dtm_mean,
            "dtm_min_m": dtm_min,
            "dtm_max_m": dtm_max,
            "estimated_building_height_m": bldg_height,
            "has_structure": str(has_structure),
            "resolution_m": res_m,
            "pixel_count": pix_cnt,
            "acquisition_date": acq_date,
            "provenance_node_id": prov_ds_id,
            "derived_from": "elevation_raster",
            "elevation_source_type": source_type,
            "quality_weight": quality_weight,
            # Land-use inference from height
            "land_use": _infer_land_use(bldg_height),
        }
        features.append({
            "geometry": geom,
            "properties": {k: (str(v) if v is not None else None) for k, v in props.items()},
            "capture_timestamp": str(acq_date) if acq_date else None,
            "provenance_node_id": prov_ds_id,
        })

    prov_nodes = [
        {
            "node_id": prov_origin_id,
            "node_type": "origin",
            "parent_ids": [],
            "label": f"Elevation source: {source_type} ({acquisition_date or 'date unknown'})",
        },
        {
            "node_id": prov_ds_id,
            "node_type": "dataset",
            "parent_ids": [prov_origin_id],
            "label": f"DSM/DTM elevation statistics ({source_type})",
        },
    ]

    n_with_structure = sum(1 for s in parcel_stats_list if s.has_structure)
    return ElevationEvidence(
        parcel_stats=parcel_stats_list,
        source_type=source_type,
        quality_weight=quality_weight,
        provenance_nodes=prov_nodes,
        features=features,
        evidence_note=(
            f"DSM/DTM elevation evidence from {source_type} "
            f"({quality_weight:.0%} quality weight). "
            f"{n_with_structure}/{len(parcel_stats_list)} parcels show structures "
            f"(building_height > {BUILDING_HEIGHT_THRESHOLD_M}m). "
            "Treated as spatial evidence — not authoritative boundary data."
        ),
    )


def from_geotiff_metadata(path: str) -> dict:
    """
    Extract spatial metadata from a GeoTIFF without loading full raster data.
    Returns CRS, bounds, resolution, band count for provenance recording.
    Requires rasterio; falls back gracefully if not installed.
    """
    try:
        import rasterio
        from rasterio.crs import CRS
        from pyproj import Transformer

        with rasterio.open(path) as src:
            crs_wkt = src.crs.to_wkt() if src.crs else None
            epsg = src.crs.to_epsg() if src.crs else None
            transform = src.transform
            width, height = src.width, src.height
            bounds = src.bounds

            # Convert bounds to WGS84
            if epsg and epsg != 4326:
                try:
                    transformer = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
                    min_lon, min_lat = transformer.transform(bounds.left, bounds.bottom)
                    max_lon, max_lat = transformer.transform(bounds.right, bounds.top)
                except Exception:
                    min_lon, min_lat = bounds.left, bounds.bottom
                    max_lon, max_lat = bounds.right, bounds.top
            else:
                min_lon, min_lat = bounds.left, bounds.bottom
                max_lon, max_lat = bounds.right, bounds.top

            resolution_x = abs(transform.a)
            resolution_y = abs(transform.e)

            return {
                "source": path,
                "crs_epsg": epsg,
                "crs_wkt": crs_wkt,
                "width_px": width,
                "height_px": height,
                "resolution_x_m": round(resolution_x, 4),
                "resolution_y_m": round(resolution_y, 4),
                "bands": src.count,
                "nodata": src.nodata,
                "wgs84_bounds": {
                    "min_lon": round(min_lon, 6),
                    "min_lat": round(min_lat, 6),
                    "max_lon": round(max_lon, 6),
                    "max_lat": round(max_lat, 6),
                },
                "extent_wgs84": {
                    "type": "Polygon",
                    "coordinates": [[
                        [min_lon, min_lat], [max_lon, min_lat],
                        [max_lon, max_lat], [min_lon, max_lat],
                        [min_lon, min_lat],
                    ]],
                },
                "rasterio_available": True,
            }
    except ImportError:
        # Graceful fallback: return minimal metadata without rasterio
        import os
        return {
            "source": path,
            "file_size_bytes": os.path.getsize(path) if os.path.exists(path) else None,
            "rasterio_available": False,
            "note": "rasterio not installed — install with: pip install rasterio",
        }
    except Exception as e:
        return {"source": path, "error": str(e), "rasterio_available": False}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _infer_land_use(building_height_m: Optional[float]) -> str:
    """Infer likely land use from building height. Low confidence — for tagging only."""
    if building_height_m is None:
        return "unknown"
    if building_height_m < 0.3:
        return "open_land"
    if building_height_m < 1.5:
        return "low_vegetation_or_rubble"
    if building_height_m < 6.0:
        return "single_storey_building"
    if building_height_m < 15.0:
        return "multi_storey_building"
    return "high_rise"
