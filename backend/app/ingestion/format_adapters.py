"""Multi-Format Ingestion Adapters — P0 Gap Closure.

Accepts: GeoJSON, Shapefile, GeoPackage, GeoParquet, CSV, GeoTIFF (metadata only).
All outputs are normalized to a canonical list of GeoJSON-style feature dicts
that feed directly into the existing ingestor pipeline.

Why this matters vs. competition:
  A.L.I.G.N. and THINK TWICE explicitly handle SHP/SHX/GeoTIFF/Parquet.
  Our backend was GeoJSON-only. This closes that gap.

Design:
  Each adapter returns List[dict] with keys:
    - geometry: GeoJSON geometry dict
    - properties: attribute dict
    - capture_timestamp: optional ISO string
    - provenance_node_id: optional
"""
from __future__ import annotations
import csv
import io
import json
import os
import tempfile
from pathlib import Path
from typing import Optional, Any

# Lazy imports so missing optional deps don't break the whole app


def _require(module: str, package: str):
    try:
        import importlib
        return importlib.import_module(module)
    except ImportError:
        raise ImportError(
            f"'{package}' is required for this format. "
            f"Install with: pip install {package}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Canonical feature builder
# ─────────────────────────────────────────────────────────────────────────────

def _canonical_feature(
    geometry: Optional[dict],
    properties: dict,
    capture_timestamp: Optional[str] = None,
    provenance_node_id: Optional[str] = None,
) -> dict:
    return {
        "geometry": geometry,
        "properties": {k: (str(v) if v is not None else None) for k, v in properties.items()},
        "capture_timestamp": capture_timestamp,
        "provenance_node_id": provenance_node_id,
    }


def _props_from_row(row: dict, date_fields: list[str] = None) -> tuple[dict, Optional[str]]:
    """Extract properties and capture_timestamp from a flat row dict."""
    date_fields = date_fields or ["date", "survey_date", "capture_date", "Date", "Survey_Date"]
    ts = None
    props = {}
    for k, v in row.items():
        if k in date_fields and v:
            ts = str(v)
        else:
            props[k] = v
    return props, ts


# ─────────────────────────────────────────────────────────────────────────────
# GeoJSON adapter (already supported — normalized wrapper)
# ─────────────────────────────────────────────────────────────────────────────

def from_geojson(data: str | bytes | dict) -> list[dict]:
    """Parse GeoJSON string/bytes/dict → canonical features."""
    if isinstance(data, (str, bytes)):
        fc = json.loads(data)
    else:
        fc = data

    if fc.get("type") == "FeatureCollection":
        features = fc.get("features", [])
    elif fc.get("type") == "Feature":
        features = [fc]
    elif isinstance(fc, list):
        features = fc
    else:
        raise ValueError(f"Unrecognised GeoJSON structure: type={fc.get('type')!r}")

    result = []
    for f in features:
        geom = f.get("geometry")
        props = f.get("properties") or {}
        ts = (
            f.get("capture_timestamp")
            or props.pop("capture_date", None)
            or props.pop("survey_date", None)
        )
        result.append(_canonical_feature(geom, props, ts))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Shapefile adapter (via fiona)
# ─────────────────────────────────────────────────────────────────────────────

def from_shapefile(path: str | Path) -> list[dict]:
    """
    Read a Shapefile (.shp) → canonical features.
    Accepts:
      - path to .shp file (sidecars .dbf/.prj/.shx must be alongside)
      - path to a ZIP containing the shapefile components
    Reprojects to WGS84 if a .prj is present.
    """
    fiona = _require("fiona", "fiona")
    import fiona.transform as ftr

    path = str(path)
    result = []
    with fiona.open(path) as src:
        src_crs = src.crs_wkt if hasattr(src, "crs_wkt") else (src.crs or {})
        needs_reproject = src_crs and "4326" not in str(src_crs)

        for feature in src:
            geom = dict(feature.geometry) if feature.geometry else None
            if geom and needs_reproject:
                try:
                    geom = ftr.transform_geom(src.crs, "EPSG:4326", geom)
                except Exception:
                    pass
            props = dict(feature.properties or {})
            props, ts = _props_from_row(props)
            result.append(_canonical_feature(geom, props, ts))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# GeoPackage adapter (via fiona, layer-aware)
# ─────────────────────────────────────────────────────────────────────────────

def from_geopackage(path: str | Path, layer: Optional[str] = None) -> list[dict]:
    """Read a GeoPackage (.gpkg) → canonical features."""
    fiona = _require("fiona", "fiona")
    import fiona.transform as ftr

    path = str(path)
    # If no layer specified, list available layers and use first
    if layer is None:
        layers = fiona.listlayers(path)
        if not layers:
            raise ValueError(f"GeoPackage {path} contains no layers")
        layer = layers[0]

    result = []
    with fiona.open(path, layer=layer) as src:
        src_crs = src.crs_wkt if hasattr(src, "crs_wkt") else (src.crs or {})
        needs_reproject = src_crs and "4326" not in str(src_crs)
        for feature in src:
            geom = dict(feature.geometry) if feature.geometry else None
            if geom and needs_reproject:
                try:
                    geom = ftr.transform_geom(src.crs, "EPSG:4326", geom)
                except Exception:
                    pass
            props = dict(feature.properties or {})
            props, ts = _props_from_row(props)
            result.append(_canonical_feature(geom, props, ts))
    return result


def list_geopackage_layers(path: str | Path) -> list[str]:
    fiona = _require("fiona", "fiona")
    return fiona.listlayers(str(path))


# ─────────────────────────────────────────────────────────────────────────────
# GeoParquet adapter (via geopandas)
# ─────────────────────────────────────────────────────────────────────────────

def from_geoparquet(path: str | Path) -> list[dict]:
    """Read a GeoParquet (.parquet) → canonical features."""
    gpd = _require("geopandas", "geopandas")
    gdf = gpd.read_parquet(str(path))
    return _gdf_to_features(gdf)


def _gdf_to_features(gdf) -> list[dict]:
    """Convert a GeoDataFrame → canonical feature list."""
    import json as _json
    # Ensure WGS84
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    result = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            geom_dict = None
        else:
            try:
                from shapely.geometry import mapping
                geom_dict = mapping(geom)
            except Exception:
                geom_dict = None

        props = {k: v for k, v in row.items() if k != "geometry"}
        props, ts = _props_from_row({k: (None if _is_na(v) else v) for k, v in props.items()})
        result.append(_canonical_feature(geom_dict, props, ts))
    return result


def _is_na(val) -> bool:
    try:
        import math
        return val is None or (isinstance(val, float) and math.isnan(val))
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# CSV adapter (tabular records with lat/lon columns)
# ─────────────────────────────────────────────────────────────────────────────

_LAT_COLS = {"lat", "latitude", "y", "lat_deg", "latitude_deg"}
_LON_COLS = {"lon", "lng", "longitude", "x", "lon_deg", "longitude_deg"}
_WKT_COLS = {"wkt", "geometry", "geom", "wkt_geometry"}


def from_csv(
    data: str | bytes | io.StringIO,
    lat_col: Optional[str] = None,
    lon_col: Optional[str] = None,
    wkt_col: Optional[str] = None,
) -> list[dict]:
    """
    Read a CSV with point or WKT geometry → canonical features.
    Auto-detects lat/lon column names if not specified.
    """
    from shapely import wkt as shapely_wkt
    from shapely.geometry import Point, mapping

    if isinstance(data, bytes):
        data = data.decode("utf-8", errors="replace")
    if isinstance(data, str):
        reader = csv.DictReader(io.StringIO(data))
    else:
        reader = csv.DictReader(data)

    rows = list(reader)
    if not rows:
        return []

    headers_lower = {h.lower(): h for h in rows[0].keys()}

    # Auto-detect geometry columns
    if wkt_col is None:
        for c in _WKT_COLS:
            if c in headers_lower:
                wkt_col = headers_lower[c]
                break

    if lat_col is None:
        for c in _LAT_COLS:
            if c in headers_lower:
                lat_col = headers_lower[c]
                break

    if lon_col is None:
        for c in _LON_COLS:
            if c in headers_lower:
                lon_col = headers_lower[c]
                break

    result = []
    for row in rows:
        geom_dict = None

        if wkt_col and row.get(wkt_col):
            try:
                g = shapely_wkt.loads(row[wkt_col])
                geom_dict = mapping(g)
            except Exception:
                pass
        elif lat_col and lon_col:
            try:
                lat = float(row[lat_col])
                lon = float(row[lon_col])
                geom_dict = mapping(Point(lon, lat))
            except (ValueError, TypeError):
                pass

        # Remove geometry columns from properties
        skip = {wkt_col, lat_col, lon_col} - {None}
        props = {k: v for k, v in row.items() if k not in skip}
        props, ts = _props_from_row(props)
        result.append(_canonical_feature(geom_dict, props, ts))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# GeoTIFF metadata adapter (raster → extent + metadata, not pixel extraction)
# ─────────────────────────────────────────────────────────────────────────────

def from_geotiff_metadata(path: str | Path) -> dict:
    """
    Extract metadata from a GeoTIFF (ORI, DSM, DTM, orthophoto).
    Returns a metadata dict; does NOT return pixel data.
    For imagery-derived feature extraction see imagery_adapter.py.
    """
    rasterio = _require("rasterio", "rasterio")
    import rasterio.crs

    path = str(path)
    with rasterio.open(path) as src:
        bounds = src.bounds
        crs = src.crs.to_string() if src.crs else "unknown"
        width, height = src.width, src.height
        bands = src.count
        dtype = str(src.dtypes[0]) if src.dtypes else "unknown"
        nodata = src.nodata
        transform = list(src.transform)

        # Approximate extent polygon (WGS84)
        try:
            from rasterio.warp import transform_bounds
            wgs_bounds = transform_bounds(src.crs, "EPSG:4326",
                                          bounds.left, bounds.bottom,
                                          bounds.right, bounds.top)
        except Exception:
            wgs_bounds = (bounds.left, bounds.bottom, bounds.right, bounds.top)

        extent_geojson = {
            "type": "Polygon",
            "coordinates": [[
                [wgs_bounds[0], wgs_bounds[1]],
                [wgs_bounds[2], wgs_bounds[1]],
                [wgs_bounds[2], wgs_bounds[3]],
                [wgs_bounds[0], wgs_bounds[3]],
                [wgs_bounds[0], wgs_bounds[1]],
            ]],
        }

    return {
        "file": Path(path).name,
        "crs": crs,
        "width_px": width,
        "height_px": height,
        "bands": bands,
        "dtype": dtype,
        "nodata": nodata,
        "bounds_native": {
            "left": bounds.left, "bottom": bounds.bottom,
            "right": bounds.right, "top": bounds.top,
        },
        "extent_wgs84": extent_geojson,
        "wgs84_bounds": {
            "west": wgs_bounds[0], "south": wgs_bounds[1],
            "east": wgs_bounds[2], "north": wgs_bounds[3],
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Auto-detect format from file extension
# ─────────────────────────────────────────────────────────────────────────────

def from_file(path: str | Path, layer: Optional[str] = None) -> list[dict]:
    """
    Auto-detect format from file extension and parse.
    Returns canonical feature list.
    """
    path = Path(path)
    ext = path.suffix.lower()

    if ext in (".geojson", ".json"):
        return from_geojson(path.read_text(encoding="utf-8"))
    elif ext == ".shp":
        return from_shapefile(path)
    elif ext == ".gpkg":
        return from_geopackage(path, layer=layer)
    elif ext == ".parquet":
        return from_geoparquet(path)
    elif ext == ".csv":
        return from_csv(path.read_text(encoding="utf-8"))
    elif ext in (".tif", ".tiff"):
        meta = from_geotiff_metadata(path)
        # Return a single feature representing the imagery extent
        return [_canonical_feature(
            meta["extent_wgs84"],
            {k: str(v) for k, v in meta.items() if k != "extent_wgs84"},
            None,
        )]
    elif ext == ".zip":
        return from_zip(path)
    else:
        raise ValueError(
            f"Unsupported file format: {ext!r}. "
            "Supported: .geojson, .json, .shp, .gpkg, .parquet, .csv, .tif/.tiff, .zip"
        )


def from_zip(path: str | Path) -> list[dict]:
    """Extract and parse the first recognisable geospatial file from a ZIP."""
    import zipfile
    path = Path(path)
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        for name in names:
            ext = Path(name).suffix.lower()
            if ext in (".geojson", ".json"):
                return from_geojson(zf.read(name).decode("utf-8"))
            elif ext == ".gpkg":
                with tempfile.NamedTemporaryFile(suffix=".gpkg", delete=False) as tmp:
                    tmp.write(zf.read(name))
                    tmp_path = tmp.name
                try:
                    return from_geopackage(tmp_path)
                finally:
                    os.unlink(tmp_path)
            elif ext == ".parquet":
                with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
                    tmp.write(zf.read(name))
                    tmp_path = tmp.name
                try:
                    return from_geoparquet(tmp_path)
                finally:
                    os.unlink(tmp_path)

        # Try shapefile (needs all components)
        shp_names = [n for n in names if n.lower().endswith(".shp")]
        if shp_names:
            with tempfile.TemporaryDirectory() as tmpdir:
                for n in names:
                    if Path(n).stem == Path(shp_names[0]).stem:
                        zf.extract(n, tmpdir)
                return from_shapefile(Path(tmpdir) / shp_names[0])

    raise ValueError(f"No recognisable geospatial file found in ZIP: {path.name}")


# ─────────────────────────────────────────────────────────────────────────────
# Format info
# ─────────────────────────────────────────────────────────────────────────────

SUPPORTED_FORMATS = {
    ".geojson": "GeoJSON FeatureCollection",
    ".json": "GeoJSON FeatureCollection",
    ".shp": "ESRI Shapefile (fiona required)",
    ".gpkg": "OGC GeoPackage (fiona required)",
    ".parquet": "GeoParquet (geopandas required)",
    ".csv": "CSV with lat/lon or WKT geometry column",
    ".tif": "GeoTIFF — extent metadata + imagery profile",
    ".tiff": "GeoTIFF — extent metadata + imagery profile",
    ".zip": "ZIP archive containing any of the above",
}
