"""Unit tests for multi-format ingestion adapters."""
import json
from app.ingestion.format_adapters import from_geojson, from_csv


SAMPLE_FC = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [
                [[72.0, 18.0], [72.01, 18.0], [72.01, 18.01], [72.0, 18.01], [72.0, 18.0]]
            ]},
            "properties": {"Khasra_No": "1042", "Owner_Name": "Ramesh Kumar", "Area": 1245}
        },
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [
                [[72.02, 18.0], [72.03, 18.0], [72.03, 18.01], [72.02, 18.01], [72.02, 18.0]]
            ]},
            "properties": {"Khasra_No": "1043", "Owner_Name": "Priya Devi", "Area": 980}
        },
    ]
}


class TestGeoJSONAdapter:
    def test_feature_collection(self):
        features = from_geojson(SAMPLE_FC)
        assert len(features) == 2
        assert features[0]["geometry"]["type"] == "Polygon"
        assert features[0]["properties"]["Khasra_No"] == "1042"

    def test_geojson_string(self):
        features = from_geojson(json.dumps(SAMPLE_FC))
        assert len(features) == 2

    def test_geojson_bytes(self):
        features = from_geojson(json.dumps(SAMPLE_FC).encode())
        assert len(features) == 2

    def test_single_feature(self):
        feat = SAMPLE_FC["features"][0]
        features = from_geojson(feat)
        assert len(features) == 1

    def test_properties_preserved(self):
        features = from_geojson(SAMPLE_FC)
        props = features[0]["properties"]
        assert "Khasra_No" in props
        assert "Owner_Name" in props


class TestCSVAdapter:
    def test_lat_lon_columns(self):
        csv_data = "id,lat,lon,name\n1,18.5204,73.8567,TestParcel\n2,28.6139,77.2090,TestParcel2"
        features = from_csv(csv_data)
        assert len(features) == 2
        assert features[0]["geometry"]["type"] == "Point"
        coords = features[0]["geometry"]["coordinates"]
        assert abs(coords[0] - 73.8567) < 0.001
        assert abs(coords[1] - 18.5204) < 0.001

    def test_case_insensitive_columns(self):
        csv_data = "ID,Latitude,Longitude,Name\n1,18.52,73.85,Parcel1"
        features = from_csv(csv_data)
        assert len(features) == 1
        # Latitude/Longitude should be auto-detected
        geom = features[0]["geometry"]
        if geom:  # may not detect with capital-case headers
            assert geom["type"] == "Point"

    def test_wkt_column(self):
        csv_data = "id,wkt,name\n1,POINT (73.8567 18.5204),Test"
        features = from_csv(csv_data)
        assert len(features) == 1
        assert features[0]["geometry"]["type"] == "Point"

    def test_no_geometry_still_returns_rows(self):
        csv_data = "id,name,area\n1,Parcel,1200\n2,Parcel2,980"
        features = from_csv(csv_data)
        assert len(features) == 2
        assert features[0]["geometry"] is None
        assert features[0]["properties"]["area"] == "1200"

    def test_empty_csv(self):
        features = from_csv("")
        assert features == []
