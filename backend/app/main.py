"""GeoSamanvay — FastAPI application entry point."""
from __future__ import annotations
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.routes_v2 import router_v2
from app.api.routes_v3 import router_v3
from app.api.routes_demo import router_demo
from app.api.routes_ml import router_ml
from app.api.auth import require_api_key
from app.api.rate_limit import check_rate_limit
from app.core.signing import init_signing
from app.models.database import get_engine


@asynccontextmanager
async def lifespan(app):
    data_dir = Path(os.environ.get("GS_DATA_DIR", Path(__file__).parents[2] / "data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    init_signing(data_dir)
    get_engine()
    # Attempt to train ML reranker at startup (no-op if LightGBM not installed)
    try:
        from app.matching.ml_reranker import ensure_model_trained
        ml_result = ensure_model_trained()
        print(f"[GeoSamanvay] ML reranker: {ml_result['status']}")
    except Exception as e:
        print(f"[GeoSamanvay] ML reranker startup skipped: {e}")
    print(f"[GeoSamanvay] Started — data_dir={data_dir}")
    yield


app = FastAPI(
    title="GeoSamanvay",
    description=(
        "Evidence-Aware Multi-Source Geospatial Harmonization Engine. "
        "SIH26013 — Team Aikta."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    allowed, retry_after = check_rate_limit(request)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": str(retry_after)},
        )
    return await call_next(request)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    try:
        await require_api_key(request)
    except Exception as exc:
        from fastapi import HTTPException
        if isinstance(exc, HTTPException):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=getattr(exc, "headers", {}) or {},
            )
        raise
    return await call_next(request)


app.include_router(router)
app.include_router(router_v2)
app.include_router(router_v3)
app.include_router(router_demo)
app.include_router(router_ml)

# Serve frontend static files if built
_static_dir = Path(__file__).parent.parent.parent / "static"
if _static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(_static_dir / "assets")), name="assets")

    @app.get("/")
    async def serve_spa():
        index = _static_dir / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return JSONResponse({"service": "GeoSamanvay", "docs": "/docs"})
else:
    @app.get("/")
    async def root():
        return {
            "service": "GeoSamanvay — Evidence-Aware Geospatial Harmonization",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/v1/health",
            "demo": "/api/v1/demo/load-ward42",
        }
