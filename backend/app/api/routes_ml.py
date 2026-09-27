"""ML model management endpoints.

POST /api/v1/ml/train   — train the LightGBM reranker
GET  /api/v1/ml/info    — model status, metrics, feature importances
POST /api/v1/ml/predict — score a single candidate pair (demo/debug)
"""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

router_ml = APIRouter(prefix="/api/v1/ml")


class PredictRequest(BaseModel):
    iou: float = 0.9
    hausdorff_m: float = 5.0
    area_ratio_diff: float = 0.02
    centroid_dist_m: float = 10.0
    identifier_score: float = 1.0
    owner_similarity: float = 0.95
    land_use_match: bool = True
    ward_match: bool = True
    temporal_gap_days: float = 365.0
    independent_lineages: int = 2
    source_quality_a: float = 0.90
    source_quality_b: float = 0.80


@router_ml.post("/train")
def train_model(n_positive: int = 2000, n_negative: int = 2000, force: bool = False):
    """
    Train the LightGBM parcel match reranker on a synthetic corpus.

    Training data: synthetic positive (same parcel, different sources) and
    negative (different parcels) pairs.  In production this would be replaced
    with manually adjudicated ground-truth pairs.

    Requires: pip install lightgbm scikit-learn
    """
    from app.matching.ml_reranker import train_and_save, _DEFAULT_MODEL_PATH, _DEFAULT_META_PATH
    import importlib
    import app.matching.ml_reranker as mlr
    # Reset cached state so a forced retrain is picked up immediately
    if force:
        mlr._booster = None
        mlr._model_loaded = False

    result = train_and_save(
        model_path=_DEFAULT_MODEL_PATH,
        meta_path=_DEFAULT_META_PATH,
        n_positive=n_positive,
        n_negative=n_negative,
    )
    if "error" in result:
        return {"status": "unavailable", "reason": result["error"]}
    return {
        "status": "trained",
        "model_path": str(_DEFAULT_MODEL_PATH),
        "metrics": result.get("metrics", {}),
        "feature_importances": result.get("feature_importances", {}),
        "note": result.get("training_note", ""),
    }


@router_ml.get("/info")
def model_info():
    """Return model status, metrics and feature importance."""
    from app.matching.ml_reranker import get_model_info
    return get_model_info()


@router_ml.post("/predict")
def predict_match(req: PredictRequest):
    """
    Score a single candidate match pair.
    Useful for demo/debug — shows exactly how the ML reranker and
    deterministic scorer combine to produce the final match score.
    """
    from app.matching.ml_reranker import rerank, extract_features, FEATURE_NAMES

    evidence = {
        "iou": req.iou,
        "hausdorff_m": req.hausdorff_m,
        "area_ratio_diff": req.area_ratio_diff,
        "centroid_dist_m": req.centroid_dist_m,
        "identifier_score": req.identifier_score,
        "owner_similarity": req.owner_similarity,
        "land_use_match": req.land_use_match,
        "ward_match": req.ward_match,
        "temporal_gap_days": req.temporal_gap_days,
        "independent_lineages": req.independent_lineages,
        "source_quality_a": req.source_quality_a,
        "source_quality_b": req.source_quality_b,
    }
    # Deterministic score: simple weighted average matching matcher.py approach
    det_score = (
        req.iou * 0.35
        + req.identifier_score * 0.25
        + req.owner_similarity * 0.15
        + (1.0 - min(1.0, req.temporal_gap_days / 3650)) * 0.10
        + (min(req.independent_lineages, 3) / 3) * 0.15
    )
    result = rerank(evidence, det_score)
    return {
        "deterministic_score": result.deterministic_score,
        "ml_score": result.ml_score,
        "final_score": result.final_score,
        "model_used": result.model_used,
        "feature_vector": dict(zip(FEATURE_NAMES, result.feature_vector)),
        "feature_contributions": result.feature_contributions,
        "explanation": result.explanation,
        "is_match": result.final_score >= 0.60,
    }
