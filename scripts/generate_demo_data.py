#!/usr/bin/env python3
"""Generate synthetic Ward 42 demo dataset.

Creates multi-source parcel data with known conflicts for the demo scenario.
All owner references are pseudonymized (OWNER-XXXX). No real PII.

Run from repo root:
    python scripts/generate_demo_data.py
"""
import json
import math
import random
import sys
from pathlib import Path

random.seed(42)

# Ward 42 centroid — near Pune, India
BASE_LON = 73.8567
BASE_LAT = 18.5204

# 1 degree ≈ 111km; 1m ≈ 0.000009 degrees
M2DEG = 1.0 / 111_000.0


def offset(lon, lat, dx_m, dy_m):
    """Offset coordinates by dx_m east, dy_m north."""
    return lon + dx_m * M2DEG, lat + dy_m * M2DEG


def rect_polygon(cx, cy, w_m, h_m, offset_x=0.0, offset_y=0.0, rotate_deg=0.0):
    """Create a rectangular polygon (GeoJSON) centered at (cx, cy)."""
    hw, hh = w_m / 2, h_m / 2
    corners = [
        (-hw + offset_x, -hh + offset_y),
        ( hw + offset_x, -hh + offset_y),
        ( hw + offset_x,  hh + offset_y),
        (-hw + offset_x,  hh + offset_y),
    ]
    if rotate_deg:
        rad = math.radians(rotate_deg)
        cos_r, sin_r = math.cos(rad), math.sin(rad)
        corners = [(x * cos_r - y * sin_r, x * sin_r + y * cos_r) for x, y in corners]

    coords = [offset(cx, cy, x, y) for x, y in corners]
    coords.append(coords[0])  # close ring
    return {"type": "Polygon", "coordinates": [coords]}


def feature(geom, props):
    return {"type": "Feature", "geometry": geom, "properties": props}


def feature_collection(features):
    return {"type": "FeatureCollection", "features": features}


def write_geojson(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Written: {path}")


OUTPUT_DIR = Path(__file__).parent.parent / "data" / "demo" / "ward42"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────────────────────
# Define parcel grid for Ward 42
# 10 parcels in a 2-row layout
# ─────────────────────────────────────────────────────────────────────────────

# Parcel layout: (khasra_no, row, col, width_m, height_m, owner_ref)
PARCEL_LAYOUT = [
    ("1038", 0, 0, 28, 45, "OWNER-0038"),
    ("1039", 0, 1, 32, 45, "OWNER-0039"),
    ("1040", 0, 2, 30, 45, "OWNER-0040"),
    ("1041", 0, 3, 25, 45, "OWNER-0041"),
    ("1042", 0, 4, 35, 45, "OWNER-1042"),   # ← focal parcel with conflicts
    ("1043", 0, 5, 28, 45, "OWNER-0043"),
    ("1044", 1, 0, 30, 42, "OWNER-0044"),
    ("1045", 1, 1, 30, 42, "OWNER-0045"),
    ("1046", 1, 2, 30, 42, "OWNER-0046"),
    ("1047", 1, 3, 30, 42, "OWNER-0047"),
]

COL_SPACING = 38   # metres between column centers
ROW_SPACING = 52   # metres between row centers
LAND_USES = ["Residential", "Residential", "Residential", "Commercial",
             "Residential", "Residential", "Residential", "Mixed-Use",
             "Residential", "Residential"]


def parcel_center(row, col):
    cx = BASE_LON + col * COL_SPACING * M2DEG
    cy = BASE_LAT + row * ROW_SPACING * M2DEG
    return cx, cy


# ─────────────────────────────────────────────────────────────────────────────
# CADASTRAL layer (2019, slight offsets from "true")
# ─────────────────────────────────────────────────────────────────────────────
print("Generating cadastral layer...")
cad_features = []
for i, (khasra, row, col, w, h, owner) in enumerate(PARCEL_LAYOUT):
    cx, cy = parcel_center(row, col)
    # Parcel 1042 has a 1.4m NE corner legacy offset
    extra_offset = (0.7, 0.7) if khasra == "1042" else (0, 0)
    geom = rect_polygon(cx, cy, w, h, extra_offset[0], extra_offset[1])
    area = w * h
    cad_features.append(feature(geom, {
        "Khasra_No": khasra,
        "Owner_Name": owner.replace("OWNER-", "Ramesh Kumar "),
        "Area": area,
        "Land_Use": LAND_USES[i],
        "Ward": "42",
        "Survey_Date": "2019-03-15",
        "Mutation_No": f"MUT-{int(khasra):05d}",
        # Canonical parcel reference for cross-source matching
        "parcel_reference": khasra,
    }))
write_geojson(OUTPUT_DIR / "cadastral.geojson", feature_collection(cad_features))


# ─────────────────────────────────────────────────────────────────────────────
# REVENUE / RoR layer (matches cadastral mostly, some area discrepancies)
# ─────────────────────────────────────────────────────────────────────────────
print("Generating revenue/RoR layer...")
rev_features = []
for i, (khasra, row, col, w, h, owner) in enumerate(PARCEL_LAYOUT):
    cx, cy = parcel_center(row, col)
    # RoR area is slightly different due to measurement method
    area_adjustment = -7 if khasra == "1042" else random.randint(-5, 5)
    geom = rect_polygon(cx, cy, w, h + area_adjustment * M2DEG * 111_000)
    area = w * h + area_adjustment
    rev_features.append(feature(geom, {
        "Khata_No": f"K-{khasra}",
        "Khatadar": owner.replace("OWNER-", "Shri "),
        "Area": max(area, 100),
        "Land_Class": LAND_USES[i],
        "Ward_No": "42",
        "Date_of_Survey": "2021-08-20",
        # Canonical parcel reference for cross-source matching
        "parcel_reference": khasra,
    }))
write_geojson(OUTPUT_DIR / "revenue_ror.geojson", feature_collection(rev_features))


# ─────────────────────────────────────────────────────────────────────────────
# MUNICIPAL GIS layer (newer digitization, different boundary for P-1042)
# ─────────────────────────────────────────────────────────────────────────────
print("Generating municipal GIS layer...")
mun_features = []
for i, (khasra, row, col, w, h, owner) in enumerate(PARCEL_LAYOUT):
    cx, cy = parcel_center(row, col)
    # Parcel 1042: municipal survey shows narrower boundary (26m vs 35m width)
    mun_w = 26 if khasra == "1042" else w
    geom = rect_polygon(cx, cy, mun_w, h)
    area = mun_w * h
    mun_features.append(feature(geom, {
        "Property_ID": f"MUN-W42-{khasra}",
        "Owner": owner,
        "Plot_Area": area,
        "Usage_Type": LAND_USES[i],
        "Zone": "42",
        "Survey_Date": "2022-11-10",
        "parcel_reference": khasra,
    }))
write_geojson(OUTPUT_DIR / "municipal_gis.geojson", feature_collection(mun_features))


# ─────────────────────────────────────────────────────────────────────────────
# DRONE ORI layer (2024, highest accuracy)
# ─────────────────────────────────────────────────────────────────────────────
print("Generating drone ORI layer...")
drone_features = []
for i, (khasra, row, col, w, h, owner) in enumerate(PARCEL_LAYOUT):
    cx, cy = parcel_center(row, col)
    # Drone uses 33m for P-1042 (different from cadastral 35m and municipal 26m)
    drone_w = 33 if khasra == "1042" else w + random.choice([-1, 0, 1])
    geom = rect_polygon(cx, cy, drone_w, h, 0.2 if khasra == "1042" else 0)
    area = drone_w * h
    drone_features.append(feature(geom, {
        "Parcel_ID": khasra,
        "Measured_Area": area,
        "Use": LAND_USES[i],
        "Acquisition_Date": "2024-02-14",
        "Accuracy_m": 0.15,
        "Flight_Height_m": 120,
        "parcel_reference": khasra,
    }))
write_geojson(OUTPUT_DIR / "drone_ori.geojson", feature_collection(drone_features))


# ─────────────────────────────────────────────────────────────────────────────
# BUILDING FOOTPRINTS
# Each parcel has 1 building; P-1042's building slightly crosses municipal boundary
# ─────────────────────────────────────────────────────────────────────────────
print("Generating building footprints...")
bld_features = []
for i, (khasra, row, col, w, h, owner) in enumerate(PARCEL_LAYOUT):
    cx, cy = parcel_center(row, col)
    # Building occupies ~60% of parcel
    bw = w * 0.6
    bh = h * 0.55
    # P-1042: building extends slightly beyond municipal (26m) into street
    bld_offset_x = 4.0 if khasra == "1042" else 0  # 4m east = crosses municipal boundary
    geom = rect_polygon(cx, cy, bw, bh, bld_offset_x)
    bld_features.append(feature(geom, {
        "building_id": f"BLD-W42-{khasra}",
        "parcel_khasra": khasra,
        "floors": random.randint(1, 4),
        "use": "Residential",
        "year_built": random.randint(2000, 2022),
    }))
write_geojson(OUTPUT_DIR / "buildings.geojson", feature_collection(bld_features))


# ─────────────────────────────────────────────────────────────────────────────
# UTILITY NETWORK
# A drainage line runs through the NE corner of P-1042
# ─────────────────────────────────────────────────────────────────────────────
print("Generating utility network...")
p1042_cx, p1042_cy = parcel_center(0, 4)
drain_start = offset(p1042_cx, p1042_cy, 15, 20)
drain_end = offset(p1042_cx, p1042_cy, 20, 30)
water_start = offset(BASE_LON, BASE_LAT, -20, -10)
water_end = offset(BASE_LON + 7 * COL_SPACING * M2DEG, BASE_LAT - 10, 0, 0)

util_features = [
    feature(
        {"type": "LineString", "coordinates": [list(drain_start), list(drain_end)]},
        {"utility_id": "DRAIN-001", "type": "drainage", "diameter_mm": 300, "year": 2015}
    ),
    feature(
        {"type": "LineString", "coordinates": [list(water_start), list(water_end)]},
        {"utility_id": "WATER-001", "type": "water_main", "diameter_mm": 150, "year": 2018}
    ),
]
write_geojson(OUTPUT_DIR / "utilities.geojson", feature_collection(util_features))


# ─────────────────────────────────────────────────────────────────────────────
# PROVENANCE graph definition (JSON, not GeoJSON)
# ─────────────────────────────────────────────────────────────────────────────
print("Generating provenance graph...")
provenance = {
    "description": "Ward 42 source provenance for case WARD42-DEMO",
    "nodes": [
        # Origins (independent sources)
        {"node_id": "ORIG-SURVEY-1999", "node_type": "origin", "parent_ids": [],
         "label": "Original 1999 Revenue Survey"},
        {"node_id": "ORIG-AERIAL-2022", "node_type": "origin", "parent_ids": [],
         "label": "2022 Aerial Survey Campaign"},
        {"node_id": "ORIG-DRONE-2024", "node_type": "origin", "parent_ids": [],
         "label": "2024 Drone ORI Campaign"},
        # Datasets derived from origins
        {"node_id": "DS-CADASTRAL", "node_type": "dataset", "parent_ids": ["ORIG-SURVEY-1999"],
         "label": "Cadastral Map 2019 (derived from 1999 survey + 2019 update)"},
        {"node_id": "DS-REVENUE", "node_type": "dataset", "parent_ids": ["ORIG-SURVEY-1999"],
         "label": "Revenue/RoR Records"},
        {"node_id": "DS-MUNICIPAL", "node_type": "dataset", "parent_ids": ["ORIG-AERIAL-2022"],
         "label": "Municipal GIS 2022"},
        {"node_id": "DS-DRONE", "node_type": "dataset", "parent_ids": ["ORIG-DRONE-2024"],
         "label": "Drone ORI Extraction 2024"},
        # Records
        {"node_id": "REC-CAD-1042", "node_type": "record", "parent_ids": ["DS-CADASTRAL"],
         "label": "Cadastral record for P-1042"},
        {"node_id": "REC-REV-1042", "node_type": "record", "parent_ids": ["DS-REVENUE"],
         "label": "Revenue record for P-1042"},
        {"node_id": "REC-MUN-1042", "node_type": "record", "parent_ids": ["DS-MUNICIPAL"],
         "label": "Municipal GIS record for P-1042"},
        {"node_id": "REC-DRN-1042", "node_type": "record", "parent_ids": ["DS-DRONE"],
         "label": "Drone-derived record for P-1042"},
    ]
}
prov_path = OUTPUT_DIR / "provenance_graph.json"
prov_path.write_text(json.dumps(provenance, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"  Written: {prov_path}")

print("\n✓ Ward 42 demo dataset generated successfully.")
print(f"  Output: {OUTPUT_DIR}")
print("\nConflicts present in this dataset:")
print("  P-1042: Boundary offset (cadastral 35m vs municipal 26m vs drone 33m)")
print("  P-1042: Area mismatch (1245 vs 1219 vs 1231 m²)")
print("  P-1042: Building footprint crosses municipal boundary by ~0.7m")
print("  P-1042: Drainage line crosses NE corner")
print("  RoR vs Cadastral: Shared origin (ORIG-SURVEY-1999) = NOT fully independent")
