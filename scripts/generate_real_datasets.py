#!/usr/bin/env python3
"""
Generate realistic multi-source geospatial datasets for SIH26013 demo.

Uses real geographic coordinates from Indian cities:
 - Ward 42, Pune (primary demo)
 - Sector 7, Nagpur
 - Layout 3, Bengaluru

Each ward has 4 conflicting source datasets:
 - Cadastral (older, with datum offsets)
 - Revenue/RoR (administrative, shares cadastral origin)
 - Municipal GIS (newer digitisation, different boundary)
 - Drone ORI (most accurate, 2024)

Plus cross-layer data:
 - Building footprints
 - Utility network
"""
import json, math, random
from pathlib import Path

random.seed(42)

BASE = Path(__file__).parent.parent / "data" / "demo"
BASE.mkdir(parents=True, exist_ok=True)

M2DEG = 1.0 / 111_000.0

def offset(lon, lat, dx_m, dy_m):
    return lon + dx_m * M2DEG, lat + dy_m * M2DEG

def rect(cx, cy, w_m, h_m, dx=0.0, dy=0.0, rot=0.0):
    hw, hh = w_m / 2, h_m / 2
    corners = [(-hw+dx,-hh+dy),(hw+dx,-hh+dy),(hw+dx,hh+dy),(-hw+dx,hh+dy)]
    if rot:
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        corners = [(x*c - y*s, x*s + y*c) for x,y in corners]
    coords = [offset(cx, cy, x, y) for x,y in corners]
    coords.append(coords[0])
    return {"type": "Polygon", "coordinates": [coords]}

def feat(geom, props):
    return {"type": "Feature", "geometry": geom, "properties": props}

def fc(features):
    return {"type": "FeatureCollection", "features": features}

def write(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"  Written: {path}")

# ── WARD 42, PUNE (Primary demo) ────────────────────────────────────────────
print("\nGenerating Ward 42, Pune…")
W42 = BASE / "ward42"

BASE_LON, BASE_LAT = 73.8567, 18.5204
COL_SPACING, ROW_SPACING = 38, 52

PARCELS = [
    ("1038",0,0,28,45,"OWNER-0038","Residential","Ramesh Kumar","रमेश कुमार"),
    ("1039",0,1,32,45,"OWNER-0039","Residential","Priya Sharma","प्रिया शर्मा"),
    ("1040",0,2,30,45,"OWNER-0040","Residential","Mohammed Arif","मोहम्मद आरिफ"),
    ("1041",0,3,25,45,"OWNER-0041","Residential","Sunita Patil","सुनीता पाटील"),
    ("1042",0,4,35,45,"OWNER-1042","Residential","Vijay Deshmukh","विजय देशमुख"),  # focal
    ("1043",0,5,28,45,"OWNER-0043","Residential","Anita Joshi","अनिता जोशी"),
    ("1044",1,0,30,42,"OWNER-0044","Commercial","Rajesh Mehta","राजेश मेहता"),
    ("1045",1,1,30,42,"OWNER-0045","Mixed-Use","Fatima Khan","फातिमा खान"),
    ("1046",1,2,30,42,"OWNER-0046","Residential","Suresh Yadav","सुरेश यादव"),
    ("1047",1,3,30,42,"OWNER-0047","Residential","Meena Iyer","मीना अय्यर"),
]

def pcenter(row, col):
    return BASE_LON + col * COL_SPACING * M2DEG, BASE_LAT + row * ROW_SPACING * M2DEG

# Cadastral — legacy datum offset on 1042
cad = []
for khasra,row,col,w,h,owner_ref,lu,name_en,name_hi in PARCELS:
    cx, cy = pcenter(row, col)
    dx = 0.7 if khasra=="1042" else 0
    dy = 0.7 if khasra=="1042" else 0
    cad.append(feat(rect(cx,cy,w,h,dx,dy), {
        "Khasra_No": khasra, "Owner_Name": name_en, "Area": w*h,
        "Land_Use": lu, "Ward": "42", "Survey_Date": "2019-03-15",
        "Mutation_No": f"MUT-0{khasra}", "parcel_reference": khasra,
    }))
write(W42/"cadastral.geojson", fc(cad))

# Revenue — derives from same 1999 survey, slight area diff
rev = []
for khasra,row,col,w,h,owner_ref,lu,name_en,name_hi in PARCELS:
    cx, cy = pcenter(row, col)
    adj = -7 if khasra=="1042" else random.randint(-5,5)
    rev.append(feat(rect(cx,cy,w,h+adj*M2DEG*111_000), {
        "Khata_No": f"K-{khasra}", "Khatadar": f"Shri {name_en}",
        "Area": max(w*h+adj, 100), "Land_Class": lu, "Ward_No": "42",
        "Date_of_Survey": "2021-08-20", "parcel_reference": khasra,
        "Devanagari_Name": name_hi,
    }))
write(W42/"revenue_ror.geojson", fc(rev))

# Municipal — narrower boundary for 1042
mun = []
for khasra,row,col,w,h,owner_ref,lu,name_en,name_hi in PARCELS:
    cx, cy = pcenter(row, col)
    mw = 26 if khasra=="1042" else w
    mun.append(feat(rect(cx,cy,mw,h), {
        "Property_ID": f"MUN-W42-{khasra}", "Owner": owner_ref,
        "Plot_Area": mw*h, "Usage_Type": lu, "Zone": "42",
        "Survey_Date": "2022-11-10", "parcel_reference": khasra,
    }))
write(W42/"municipal_gis.geojson", fc(mun))

# Drone ORI — 33m wide on 1042, 0.2m east shift
drone = []
for khasra,row,col,w,h,owner_ref,lu,name_en,name_hi in PARCELS:
    cx, cy = pcenter(row, col)
    dw = 33 if khasra=="1042" else w + random.choice([-1,0,1])
    dx = 0.2 if khasra=="1042" else 0
    drone.append(feat(rect(cx,cy,dw,h,dx), {
        "Parcel_ID": khasra, "Measured_Area": dw*h, "Use": lu,
        "Acquisition_Date": "2024-02-14", "Accuracy_m": 0.15,
        "Flight_Height_m": 120, "parcel_reference": khasra,
    }))
write(W42/"drone_ori.geojson", fc(drone))

# Buildings — 1042's building crosses municipal boundary
bld = []
for khasra,row,col,w,h,owner_ref,lu,name_en,name_hi in PARCELS:
    cx, cy = pcenter(row, col)
    bx = 4.0 if khasra=="1042" else 0  # intentional crossing
    bld.append(feat(rect(cx,cy,w*0.6,h*0.55,bx), {
        "building_id": f"BLD-W42-{khasra}", "parcel_khasra": khasra,
        "floors": random.randint(1,4), "use": "Residential",
        "year_built": random.randint(2000,2022),
    }))
write(W42/"buildings.geojson", fc(bld))

# Utilities
cx42, cy42 = pcenter(0, 4)
drain_start = offset(cx42, cy42, 15, 20)
drain_end   = offset(cx42, cy42, 20, 30)
water_start = offset(BASE_LON, BASE_LAT, -20, -10)
water_end   = offset(BASE_LON + 7*COL_SPACING*M2DEG, BASE_LAT-10, 0, 0)
utils = [
    feat({"type":"LineString","coordinates":[list(drain_start),list(drain_end)]},
         {"utility_id":"DRAIN-001","type":"drainage","diameter_mm":300}),
    feat({"type":"LineString","coordinates":[list(water_start),list(water_end)]},
         {"utility_id":"WATER-001","type":"water_main","diameter_mm":150}),
]
write(W42/"utilities.geojson", fc(utils))

# Provenance
prov = {"nodes": [
    {"node_id":"ORIG-SURVEY-1999","node_type":"origin","parent_ids":[],"label":"Original 1999 Revenue Survey"},
    {"node_id":"ORIG-AERIAL-2022","node_type":"origin","parent_ids":[],"label":"2022 Aerial Survey Campaign"},
    {"node_id":"ORIG-DRONE-2024","node_type":"origin","parent_ids":[],"label":"2024 Drone ORI Campaign"},
    {"node_id":"DS-CADASTRAL","node_type":"dataset","parent_ids":["ORIG-SURVEY-1999"],"label":"Cadastral Map 2019"},
    {"node_id":"DS-REVENUE","node_type":"dataset","parent_ids":["ORIG-SURVEY-1999"],"label":"Revenue/RoR Records"},
    {"node_id":"DS-MUNICIPAL","node_type":"dataset","parent_ids":["ORIG-AERIAL-2022"],"label":"Municipal GIS 2022"},
    {"node_id":"DS-DRONE","node_type":"dataset","parent_ids":["ORIG-DRONE-2024"],"label":"Drone ORI Extraction 2024"},
    {"node_id":"REC-CAD-1042","node_type":"record","parent_ids":["DS-CADASTRAL"],"label":"Cadastral record P-1042"},
    {"node_id":"REC-REV-1042","node_type":"record","parent_ids":["DS-REVENUE"],"label":"Revenue record P-1042"},
    {"node_id":"REC-MUN-1042","node_type":"record","parent_ids":["DS-MUNICIPAL"],"label":"Municipal record P-1042"},
    {"node_id":"REC-DRN-1042","node_type":"record","parent_ids":["DS-DRONE"],"label":"Drone record P-1042"},
]}
write(W42/"provenance_graph.json", prov)
print("  Ward 42 Pune: 10 parcels, 4 conflicting sources, buildings, utilities, provenance")


# ── SECTOR 7, NAGPUR (Second demo case) ────────────────────────────────────
print("\nGenerating Sector 7, Nagpur…")
N7 = BASE / "nagpur_sector7"
N_LON, N_LAT = 79.0882, 21.1458
N_PARCELS = [
    ("N-201",0,0,40,55,"OWNER-N201","Residential","Rajkumar Singh"),
    ("N-202",0,1,38,55,"OWNER-N202","Residential","Lakshmi Reddy"),
    ("N-203",0,2,42,55,"OWNER-N203","Commercial","Ashok Gupta"),
    ("N-204",0,3,36,55,"OWNER-N204","Residential","Deepa Naidu"),
    ("N-205",1,0,40,48,"OWNER-N205","Residential","Prakash Wankhede"),
    ("N-206",1,1,40,48,"OWNER-N206","Mixed-Use","Shalini Bhosle"),
]

n_cad, n_rev, n_mun, n_drone = [], [], [], []
for pid,row,col,w,h,owner,lu,name in N_PARCELS:
    cx = N_LON + col * 45 * M2DEG
    cy = N_LAT + row * 58 * M2DEG
    # Cadastral: 1.1m offset on N-203
    dx = 1.1 if pid=="N-203" else 0
    n_cad.append(feat(rect(cx,cy,w,h,dx), {
        "Khasra_No": pid, "Owner_Name": name, "Area": w*h,
        "Land_Use": lu, "Ward": "7", "Survey_Date": "2018-05-20",
        "parcel_reference": pid,
    }))
    n_rev.append(feat(rect(cx,cy,w,h), {
        "Khata_No": f"K-{pid}", "Khatadar": name, "Area": w*h - random.randint(3,15),
        "Land_Class": lu, "Ward_No": "7", "Date_of_Survey": "2020-09-15",
        "parcel_reference": pid,
    }))
    mw = 32 if pid=="N-203" else w
    n_mun.append(feat(rect(cx,cy,mw,h), {
        "Property_ID": f"NMC-{pid}", "Owner": owner, "Plot_Area": mw*h,
        "Usage_Type": lu, "Zone": "7", "Survey_Date": "2023-03-10",
        "parcel_reference": pid,
    }))
    dw = 38 if pid=="N-203" else w
    n_drone.append(feat(rect(cx,cy,dw,h,0.3 if pid=="N-203" else 0), {
        "Parcel_ID": pid, "Measured_Area": dw*h, "Use": lu,
        "Acquisition_Date": "2024-06-20", "Accuracy_m": 0.12,
        "parcel_reference": pid,
    }))

write(N7/"cadastral.geojson", fc(n_cad))
write(N7/"revenue_ror.geojson", fc(n_rev))
write(N7/"municipal_gis.geojson", fc(n_mun))
write(N7/"drone_ori.geojson", fc(n_drone))

n_prov = {"nodes": [
    {"node_id":"ORIG-NAGPUR-SURVEY-2017","node_type":"origin","parent_ids":[],"label":"Nagpur Survey 2017"},
    {"node_id":"ORIG-NAGPUR-SAT-2023","node_type":"origin","parent_ids":[],"label":"Nagpur Satellite 2023"},
    {"node_id":"ORIG-NAGPUR-DRONE-2024","node_type":"origin","parent_ids":[],"label":"Nagpur Drone 2024"},
    {"node_id":"DS-N-CAD","node_type":"dataset","parent_ids":["ORIG-NAGPUR-SURVEY-2017"],"label":"Nagpur Cadastral"},
    {"node_id":"DS-N-REV","node_type":"dataset","parent_ids":["ORIG-NAGPUR-SURVEY-2017"],"label":"Nagpur RoR"},
    {"node_id":"DS-N-MUN","node_type":"dataset","parent_ids":["ORIG-NAGPUR-SAT-2023"],"label":"Nagpur Municipal GIS"},
    {"node_id":"DS-N-DRN","node_type":"dataset","parent_ids":["ORIG-NAGPUR-DRONE-2024"],"label":"Nagpur Drone"},
]}
write(N7/"provenance_graph.json", n_prov)
print("  Nagpur Sector 7: 6 parcels, N-203 has 1.1m boundary conflict")


# ── LAYOUT 3, BENGALURU (Third case — encroachment scenario) ────────────────
print("\nGenerating Layout 3, Bengaluru…")
B3 = BASE / "bengaluru_layout3"
B_LON, B_LAT = 77.5946, 12.9716

B_PARCELS = [
    ("B-301",0,0,45,60,"OWNER-B301","Residential","Venkatesh Rao"),
    ("B-302",0,1,45,60,"OWNER-B302","Residential","Kavitha Nair"),
    ("B-303",0,2,45,60,"OWNER-B303","Commercial","Ibrahim Sheikh"),
    ("B-304",1,0,45,55,"OWNER-B304","Residential","Padma Swamy"),
    ("B-305",1,1,45,55,"OWNER-B305","Residential","Geetha Pillai"),
]

b_cad, b_rev, b_mun, b_drone = [], [], [], []
for pid,row,col,w,h,owner,lu,name in B_PARCELS:
    cx = B_LON + col * 50 * M2DEG
    cy = B_LAT + row * 62 * M2DEG
    # B-303 has larger encroachment situation
    dx = 2.1 if pid=="B-303" else 0
    b_cad.append(feat(rect(cx,cy,w,h,dx), {
        "Survey_No": pid, "Owner_Name": name, "Area": w*h,
        "Land_Use": lu, "Ward": "Layout3", "Survey_Date": "2016-11-12",
        "parcel_reference": pid,
    }))
    b_rev.append(feat(rect(cx,cy,w,h), {
        "Mutation_No": f"M-{pid}", "Pattadar": name, "Extent": w*h - random.randint(5,20),
        "Classification": lu, "Hobli": "Layout3", "Survey_Date": "2019-04-08",
        "parcel_reference": pid,
    }))
    mw = 38 if pid=="B-303" else w
    b_mun.append(feat(rect(cx,cy,mw,h), {
        "Khata_No": f"BBMP-{pid}", "Owner": owner, "Site_Area": mw*h,
        "Usage": lu, "Ward": "Layout3", "Survey_Date": "2022-07-19",
        "parcel_reference": pid,
    }))
    dw = 43 if pid=="B-303" else w
    b_drone.append(feat(rect(cx,cy,dw,h), {
        "Parcel_ID": pid, "Area": dw*h, "Use": lu,
        "Date": "2024-09-05", "GSD_cm": 8,
        "parcel_reference": pid,
    }))

write(B3/"cadastral.geojson", fc(b_cad))
write(B3/"revenue_ror.geojson", fc(b_rev))
write(B3/"municipal_gis.geojson", fc(b_mun))
write(B3/"drone_ori.geojson", fc(b_drone))

b_prov = {"nodes": [
    {"node_id":"ORIG-BBMP-SURVEY-2015","node_type":"origin","parent_ids":[],"label":"BBMP Ground Survey 2015"},
    {"node_id":"ORIG-KSCB-2022","node_type":"origin","parent_ids":[],"label":"Karnataka Satellite 2022"},
    {"node_id":"ORIG-BLR-DRONE-2024","node_type":"origin","parent_ids":[],"label":"Bengaluru UAV Survey 2024"},
    {"node_id":"DS-B-CAD","node_type":"dataset","parent_ids":["ORIG-BBMP-SURVEY-2015"],"label":"BBMP Cadastral"},
    {"node_id":"DS-B-REV","node_type":"dataset","parent_ids":["ORIG-BBMP-SURVEY-2015"],"label":"Revenue Pattadar"},
    {"node_id":"DS-B-MUN","node_type":"dataset","parent_ids":["ORIG-KSCB-2022"],"label":"BBMP GIS 2022"},
    {"node_id":"DS-B-DRN","node_type":"dataset","parent_ids":["ORIG-BLR-DRONE-2024"],"label":"UAV Survey 2024"},
]}
write(B3/"provenance_graph.json", b_prov)
print("  Bengaluru Layout 3: 5 parcels, B-303 encroachment scenario (2.1m)")


print("\n✓ All real datasets generated.")
print(f"  Ward 42 Pune      : {W42}")
print(f"  Nagpur Sector 7   : {N7}")
print(f"  Bengaluru Layout 3: {B3}")
