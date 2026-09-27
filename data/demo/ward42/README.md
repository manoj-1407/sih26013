# Ward 42 — Demo Dataset

Synthetic but realistic multi-source urban land parcel data
for a hypothetical Ward 42 in an Indian city (~Pune/Nagpur context).

## Scenario

Parcel P-1042 is the focal parcel with the following data conflict:

| Source            | Area    | Boundary Status      |
|-------------------|---------|----------------------|
| Cadastral (2019)  | 1,245 m²| Legacy survey, 1.4m offset in NE corner |
| Revenue/RoR       | 1,238 m²| Matches cadastral mostly |
| Municipal GIS     | 1,219 m²| Newer digitization, different datum |
| Drone ORI (2024)  | 1,231 m²| Most recent, high accuracy |
| Building footprint| —       | Crosses municipal boundary by 0.7m |
| Drain (utility)   | —       | Crosses NE corner of parcel |

## Files

- `cadastral.geojson` — 10 cadastral parcels
- `revenue_ror.geojson` — Revenue/RoR records
- `municipal_gis.geojson` — Municipal GIS parcels
- `drone_ori.geojson` — Drone-derived parcel boundaries
- `buildings.geojson` — Building footprints
- `utilities.geojson` — Utility network (drains, water lines)
- `neighbors.geojson` — Neighboring parcels for ripple check

All coordinates in WGS84 (EPSG:4326).
Owner names use pseudonymized references (OWNER-XXXX).
No real PII is present in this dataset.
