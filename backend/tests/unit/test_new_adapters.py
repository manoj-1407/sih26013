"""Unit tests for new PS26013 gap-closure adapters.

Tests:
  - elevation_adapter: DSM/DTM stats, building height, land use inference
  - gnss_adapter: CSV/JSON/GeoJSON parsing, accuracy model
  - ground_truth_adapter: GeoJSON/CSV/JSON parsing, category normalisation
  - schema_normalizer: new DSM/GNSS/GT field aliases
  - domain: new SourceType values
"""
import pytest


# ─────────────────────────────────────────────────────────────────────────────
# elevation_adapter
# ─────────────────────────────────────────────────────────────────────────────

class TestElevationAdapter:
    def test_basic_stats_ingested(self):
        from app.ingestion.elevation_adapter import adapt_elevation_stats

        stats = [
            {
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[73.85, 18.52], [73.86, 18.52],
                                     [73.86, 18.53], [73.85, 18.53], [73.85, 18.52]]]
                },
                "dsm_mean_m": 563.4,
                "dtm_mean_m": 558.1,
                "dsm_max_m": 571.2,
                "dtm_max_m": 559.0,
                "resolution_m": 0.10,
                "parcel_id": "P-1042",
                "acquisition_date": "2024-02-14",
            }
        ]
        result = adapt_elevation_stats(stats, source_type="drone_photogrammetry")
        assert len(result.features) == 1
        assert result.quality_weight == pytest.approx(0.92, abs=0.01)
        assert len(result.parcel_stats) == 1

        s = result.parcel_stats[0]
        assert s.dsm_mean_m == pytest.approx(563.4, abs=0.01)
        assert s.dtm_mean_m == pytest.approx(558.1, abs=0.01)
        assert s.estimated_building_height_m == pytest.approx(5.3, abs=0.05)
        assert s.has_structure is True  # 5.3m > threshold 1.5m

    def test_no_structure_when_height_low(self):
        from app.ingestion.elevation_adapter import adapt_elevation_stats

        stats = [{
            "geometry": {"type": "Polygon", "coordinates": [[[73.85, 18.52], [73.86, 18.52],
                         [73.86, 18.53], [73.85, 18.53], [73.85, 18.52]]]},
            "dsm_mean_m": 100.8,
            "dtm_mean_m": 100.5,
        }]
        result = adapt_elevation_stats(stats, source_type="unknown")
        assert result.parcel_stats[0].has_structure is False  # 0.3m < 1.5m threshold

    def test_provenance_nodes_created(self):
        from app.ingestion.elevation_adapter import adapt_elevation_stats
        stats = [{"geometry": {"type": "Polygon", "coordinates": [[[73.0, 18.0], [73.1, 18.0],
                  [73.1, 18.1], [73.0, 18.1], [73.0, 18.0]]]}, "dsm_mean_m": 50.0, "dtm_mean_m": 48.0}]
        result = adapt_elevation_stats(stats, source_type="lidar")
        assert len(result.provenance_nodes) == 2
        assert result.provenance_nodes[0]["node_type"] == "origin"
        assert result.provenance_nodes[1]["node_type"] == "dataset"

    def test_land_use_inference(self):
        from app.ingestion.elevation_adapter import _infer_land_use
        assert _infer_land_use(0.0) == "open_land"
        assert _infer_land_use(3.5) == "single_storey_building"
        assert _infer_land_use(10.0) == "multi_storey_building"
        assert _infer_land_use(20.0) == "high_rise"
        assert _infer_land_use(None) == "unknown"

    def test_feature_properties_populated(self):
        from app.ingestion.elevation_adapter import adapt_elevation_stats
        stats = [{
            "geometry": {"type": "Polygon", "coordinates": [[[73.0, 18.0], [73.1, 18.0],
                         [73.1, 18.1], [73.0, 18.1], [73.0, 18.0]]]},
            "dsm_mean_m": 563.4, "dtm_mean_m": 558.1,
            "parcel_id": "TEST-42", "acquisition_date": "2024-01-01",
        }]
        result = adapt_elevation_stats(stats, source_type="drone_photogrammetry")
        props = result.features[0]["properties"]
        assert props["dsm_mean_m"] is not None
        assert props["estimated_building_height_m"] is not None
        assert props["has_structure"] == "True"
        assert props["parcel_reference"] == "TEST-42"


# ─────────────────────────────────────────────────────────────────────────────
# gnss_adapter
# ─────────────────────────────────────────────────────────────────────────────

class TestGNSSAdapter:
    _CSV = (
        "point_id,lon,lat,height_m,method,accuracy_m,station_id,epoch,parcel\n"
        "BM-001,73.8567,18.5202,558.2,rtk_cors,0.02,PUNE-CORS-01,2025-01-10,FP-1042\n"
        "BM-002,73.8570,18.5202,558.5,rtk_cors,0.02,PUNE-CORS-01,2025-01-10,FP-1042\n"
        "BM-003,73.8570,18.5205,558.3,rtk_cors,0.03,PUNE-CORS-01,2025-01-10,FP-1042\n"
    )

    def test_csv_parsing(self):
        from app.ingestion.gnss_adapter import adapt_gnss_csv
        result = adapt_gnss_csv(self._CSV, method="rtk_cors")
        assert len(result.observations) == 3
        assert result.observations[0].lon == pytest.approx(73.8567, abs=0.0001)
        assert result.observations[0].lat == pytest.approx(18.5202, abs=0.0001)

    def test_rtk_quality_weight(self):
        from app.ingestion.gnss_adapter import adapt_gnss_csv, GNSS_METHOD_QUALITY
        result = adapt_gnss_csv(self._CSV, method="rtk_cors")
        for obs in result.observations:
            assert obs.quality_weight >= GNSS_METHOD_QUALITY["rtk_cors"] - 0.01

    def test_accuracy_estimation_with_pdop(self):
        from app.ingestion.gnss_adapter import _estimate_accuracy
        # High PDOP should increase uncertainty
        acc_good = _estimate_accuracy("rtk_cors", pdop=1.5, baseline_km=None)
        acc_bad  = _estimate_accuracy("rtk_cors", pdop=6.0, baseline_km=None)
        assert acc_bad > acc_good

    def test_json_parsing(self):
        from app.ingestion.gnss_adapter import adapt_gnss_json
        data = [
            {"point_id": "P1", "lon": 73.856, "lat": 18.520,
             "method": "dgnss", "epoch": "2024-06-01", "parcel": "T-001"},
        ]
        result = adapt_gnss_json(data, method="dgnss")
        assert len(result.observations) == 1
        assert result.observations[0].method == "dgnss"

    def test_geojson_parsing(self):
        from app.ingestion.gnss_adapter import adapt_gnss_geojson
        gj = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature",
                 "geometry": {"type": "Point", "coordinates": [73.856, 18.520, 558.0]},
                 "properties": {"point_id": "P1", "method": "rtk_local",
                                "accuracy_m": "0.05"}},
            ],
        }
        result = adapt_gnss_geojson(gj, method="rtk_local")
        assert len(result.observations) == 1
        assert result.observations[0].height_m == pytest.approx(558.0, abs=0.01)

    def test_provenance_nodes_independent_origin(self):
        from app.ingestion.gnss_adapter import adapt_gnss_json
        result = adapt_gnss_json([{"point_id": "X", "lon": 73.0, "lat": 18.0}])
        origins = [n for n in result.provenance_nodes if n["node_type"] == "origin"]
        assert len(origins) == 1
        assert origins[0]["node_id"].startswith("ORIG-GNSS-")

    def test_low_accuracy_reduces_quality_weight(self):
        from app.ingestion.gnss_adapter import adapt_gnss_json
        result = adapt_gnss_json([
            {"point_id": "P1", "lon": 73.0, "lat": 18.0,
             "method": "autonomous", "accuracy_m": "5.0"},
        ])
        assert result.observations[0].quality_weight <= 0.60


# ─────────────────────────────────────────────────────────────────────────────
# ground_truth_adapter
# ─────────────────────────────────────────────────────────────────────────────

class TestGroundTruthAdapter:
    _GEOJSON = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": [73.856, 18.520]},
             "properties": {
                 "obs_id": "GT-001", "category": "building_present",
                 "value": "single_storey_residential",
                 "confidence": "0.95", "operator": "S. Patil",
                 "date": "2025-01-15", "parcel": "FP-1042",
                 "supports": "DRONE_ORI",
             }},
            {"type": "Feature",
             "geometry": {"type": "Point", "coordinates": [73.857, 18.521]},
             "properties": {
                 "obs_id": "GT-002", "category": "land_use",
                 "value": "Residential", "confidence": "0.90",
             }},
        ],
    }

    def test_geojson_parsing(self):
        from app.ingestion.ground_truth_adapter import adapt_gt_geojson
        result = adapt_gt_geojson(self._GEOJSON, operator="Test Operator")
        assert len(result.observations) == 2
        assert result.observations[0].category == "building_present"
        assert result.observations[0].confidence == pytest.approx(0.95, abs=0.01)
        assert result.observations[0].supports_source == "DRONE_ORI"
        assert result.observations[1].category == "land_use"

    def test_csv_parsing(self):
        from app.ingestion.ground_truth_adapter import adapt_gt_csv
        csv_data = (
            "obs_id,lat,lon,category,value,confidence,operator,date,parcel\n"
            "GT-001,18.520,73.856,building_present,yes,0.95,S. Patil,2025-01-15,FP-1042\n"
            "GT-002,18.521,73.857,no_building,,0.90,S. Patil,2025-01-15,FP-1043\n"
        )
        result = adapt_gt_csv(csv_data)
        assert len(result.observations) == 2
        assert result.observations[1].category == "no_building"

    def test_category_normalisation(self):
        from app.ingestion.ground_truth_adapter import _normalise_category
        assert _normalise_category("Building Present") == "building_present"
        assert _normalise_category("LAND_USE") == "land_use"
        assert _normalise_category("unknown_xyz") == "other"
        assert _normalise_category(None) == "other"

    def test_has_structure_inference(self):
        from app.ingestion.ground_truth_adapter import adapt_gt_geojson
        gj = {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature",
                 "geometry": {"type": "Point", "coordinates": [73.0, 18.0]},
                 "properties": {"obs_id": "X", "category": "building_present"}},
            ],
        }
        result = adapt_gt_geojson(gj)
        props = result.features[0]["properties"]
        assert props.get("has_structure") == "true"

    def test_independent_provenance_origin(self):
        from app.ingestion.ground_truth_adapter import adapt_gt_json
        result = adapt_gt_json([
            {"obs_id": "X", "lat": 18.0, "lon": 73.0, "category": "open_land"},
        ])
        origins = [n for n in result.provenance_nodes if n["node_type"] == "origin"]
        assert len(origins) == 1
        assert origins[0]["node_id"].startswith("ORIG-GT-")

    def test_default_confidence_applied(self):
        from app.ingestion.ground_truth_adapter import adapt_gt_json
        result = adapt_gt_json(
            [{"obs_id": "Y", "lat": 18.0, "lon": 73.0}],
            default_confidence=0.85,
        )
        assert result.observations[0].confidence == pytest.approx(0.85, abs=0.01)


# ─────────────────────────────────────────────────────────────────────────────
# schema_normalizer — new aliases
# ─────────────────────────────────────────────────────────────────────────────

class TestSchemaNormalizerNewAliases:
    def test_dsm_dtm_aliases_mapped(self):
        from app.ingestion.schema_normalizer import normalize_attributes
        attrs = {
            "dsm_mean_m": 563.4, "dtm_mean_m": 558.1,
            "estimated_building_height_m": 5.3, "has_structure": "true",
        }
        result = normalize_attributes(attrs, source_type="DSM_DTM")
        assert result.canonical.get("dsm_mean_m") is not None
        assert result.canonical.get("dtm_mean_m") is not None

    def test_gnss_aliases_mapped(self):
        from app.ingestion.schema_normalizer import normalize_attributes
        attrs = {
            "gnss_method": "rtk_cors",
            "horizontal_accuracy_m": "0.02",
            "pdop": "1.5",
            "cors_station": "PUNE-CORS-01",
        }
        result = normalize_attributes(attrs, source_type="GNSS_SURVEY")
        assert result.canonical.get("gnss_method") == "rtk_cors"
        assert result.canonical.get("horizontal_accuracy_m") == "0.02"

    def test_gt_aliases_mapped(self):
        from app.ingestion.schema_normalizer import normalize_attributes
        attrs = {
            "gt_category": "building_present",
            "gt_confidence": "0.95",
            "observed_value": "single_storey",
        }
        result = normalize_attributes(attrs, source_type="GROUND_TRUTH")
        assert result.canonical.get("gt_category") == "building_present"
        assert result.canonical.get("gt_confidence") == "0.95"


# ─────────────────────────────────────────────────────────────────────────────
# domain model — new SourceTypes
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainModel:
    def test_ground_truth_source_type_exists(self):
        from app.models.domain import SourceType
        assert SourceType.GROUND_TRUTH == "GROUND_TRUTH"

    def test_dsm_dtm_source_type_exists(self):
        from app.models.domain import SourceType
        assert SourceType.DSM_DTM == "DSM_DTM"

    def test_source_quality_weights_include_new_types(self):
        from app.harmonization.proposer import SOURCE_QUALITY_WEIGHTS
        assert "GROUND_TRUTH" in SOURCE_QUALITY_WEIGHTS
        assert "DSM_DTM" in SOURCE_QUALITY_WEIGHTS
        # Ground truth should be higher weight than municipal
        assert SOURCE_QUALITY_WEIGHTS["GROUND_TRUTH"] > SOURCE_QUALITY_WEIGHTS["MUNICIPAL_GIS"]
        # DSM_DTM higher than historical
        assert SOURCE_QUALITY_WEIGHTS["DSM_DTM"] > SOURCE_QUALITY_WEIGHTS["HISTORICAL"]
