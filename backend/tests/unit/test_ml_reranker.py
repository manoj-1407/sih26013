"""Unit tests for the LightGBM ML reranker module.

These tests run whether or not LightGBM is installed:
- With LightGBM: full training + inference path
- Without LightGBM: graceful fallback to deterministic score
"""
import pytest
import numpy as np
from app.matching.ml_reranker import (
    extract_features, FEATURE_NAMES, N_FEATURES,
    generate_synthetic_training_data,
    rerank, get_model_info, MLMatchResult,
    _HAS_LGB,
)


class TestFeatureExtraction:
    def test_correct_length(self):
        fv = extract_features({})
        assert len(fv) == N_FEATURES

    def test_all_in_range(self):
        fv = extract_features({
            "iou": 0.95, "hausdorff_m": 5.0, "area_ratio_diff": 0.02,
            "centroid_dist_m": 10.0, "identifier_score": 1.0,
            "owner_similarity": 0.95, "land_use_match": True,
            "ward_match": True, "temporal_gap_days": 365.0,
            "independent_lineages": 3, "source_quality_a": 0.9,
            "source_quality_b": 0.8,
        })
        for i, v in enumerate(fv):
            if i == 9:  # independent_lineages (0-5)
                assert 0 <= v <= 5, f"Feature {FEATURE_NAMES[i]}={v} out of range"
            else:
                assert 0.0 <= v <= 1.0, f"Feature {FEATURE_NAMES[i]}={v} out of range"

    def test_feature_names_match_count(self):
        assert len(FEATURE_NAMES) == N_FEATURES

    def test_missing_keys_use_defaults(self):
        fv = extract_features({})
        assert len(fv) == N_FEATURES
        # No crash, all finite
        for v in fv:
            assert not (v != v)  # not NaN

    def test_clipping(self):
        fv = extract_features({"hausdorff_m": 9999, "iou": 2.0, "area_ratio_diff": -1.0})
        assert fv[0] <= 1.0   # iou clipped
        assert fv[1] <= 1.0   # hausdorff_norm clipped
        assert fv[2] >= 0.0   # area_diff clipped


class TestSyntheticData:
    def test_shape(self):
        X, y = generate_synthetic_training_data(100, 100)
        assert X.shape == (200, N_FEATURES)
        assert y.shape == (200,)

    def test_label_balance(self):
        X, y = generate_synthetic_training_data(200, 200)
        assert y.sum() == 200        # positives
        assert (y == 0).sum() == 200 # negatives

    def test_positive_higher_iou(self):
        """Positive examples should have higher average IoU than negatives."""
        X, y = generate_synthetic_training_data(500, 500, seed=7)
        pos_iou = X[y == 1, 0].mean()
        neg_iou = X[y == 0, 0].mean()
        assert pos_iou > neg_iou, "Positive pairs should have higher IoU"


class TestReranker:
    def test_fallback_when_no_model(self, tmp_path):
        """Without a trained model, rerank returns deterministic score."""
        det = 0.75
        result = rerank({"iou": 0.9}, det, model_path=tmp_path / "none.txt",
                        meta_path=tmp_path / "none.json")
        assert isinstance(result, MLMatchResult)
        assert result.final_score == det
        assert not result.model_used

    def test_result_structure(self, tmp_path):
        result = rerank({}, 0.5, model_path=tmp_path / "none.txt",
                        meta_path=tmp_path / "none.json")
        assert hasattr(result, "ml_score")
        assert hasattr(result, "deterministic_score")
        assert hasattr(result, "final_score")
        assert hasattr(result, "feature_vector")
        assert hasattr(result, "explanation")
        assert len(result.feature_vector) == N_FEATURES

    def test_explanation_is_list(self, tmp_path):
        result = rerank({"iou": 0.95, "identifier_score": 1.0}, 0.8,
                        model_path=tmp_path / "none.txt",
                        meta_path=tmp_path / "none.json")
        assert isinstance(result.explanation, list)

    @pytest.mark.skipif(not _HAS_LGB, reason="LightGBM not installed")
    def test_train_and_infer(self, tmp_path):
        """With LightGBM: train a small model and run inference."""
        from app.matching.ml_reranker import train_and_save
        mp = tmp_path / "model.txt"
        jp = tmp_path / "meta.json"
        meta = train_and_save(mp, jp, n_positive=200, n_negative=200)
        assert "metrics" in meta
        assert meta["metrics"]["precision"] > 0
        assert meta["metrics"]["recall"] > 0

        # Load the freshly trained model
        import app.matching.ml_reranker as mlr
        mlr._booster = None
        mlr._model_loaded = False
        result = rerank(
            {"iou": 0.95, "hausdorff_m": 5, "identifier_score": 1.0,
             "owner_similarity": 0.9, "independent_lineages": 2},
            0.85,
            model_path=mp, meta_path=jp,
        )
        assert result.model_used
        assert 0.0 <= result.ml_score <= 1.0
        assert 0.0 <= result.final_score <= 1.0
        assert len(result.explanation) > 0


class TestModelInfo:
    def test_returns_dict(self):
        info = get_model_info()
        assert isinstance(info, dict)
        assert "available" in info
