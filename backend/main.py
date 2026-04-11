"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          NexusScope  —  OSINT Aggregation Engine  (App Factory)             ║
║  This file is intentionally lean: only app creation, middleware, router     ║
║  registration, and lifecycle hooks live here.                               ║
║                                                                             ║
║  Feature modules → app/api/endpoints/                                       ║
║  Core services   → app/core/                                                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ── Core service modules ──────────────────────────────────────────────────────
from app.core.config import (
    APP_NAME, APP_VERSION, DEBUG,
    API_HOST, API_PORT, CORS_ORIGINS,
)
from app.core.database import init_db, close_db
from app.core.firebase import init_firebase
from database import initialize_pool, close_pool  # S3 hunting DB pool

# ── Feature routers ───────────────────────────────────────────────────────────
from app.api.endpoints.investigations import router as investigations_router
from app.api.endpoints.theater1       import router as theater1_router
from app.api.endpoints.theater2       import router as theater2_router
from app.api.endpoints.theater3       import router as theater3_router
from app.api.endpoints.theater4       import router as theater4_router
from app.api.endpoints.bot            import router as bot_router
from app.api.endpoints.intel          import router as intel_router
from app.api.endpoints.s3_leaks       import router as s3_router

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("nexusscope")


# ── Health response model ─────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status:    str = Field(..., example="healthy")
    service:   str = Field(..., example=APP_NAME)
    version:   str = Field(..., example=APP_VERSION)
    timestamp: str


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title=f"{APP_NAME} — OSINT Aggregation Engine",
    version=APP_VERSION,
    debug=DEBUG,
    description=(
        f"**{APP_NAME}** is an industrial-grade, asynchronous OSINT aggregation platform.\n\n"
        "| Theater | Capability |\n"
        "|---------|------------|\n"
        "| I   | Dark Web / Onion crawling & Ahmia search |\n"
        "| II  | Domain DNS, IP intelligence, Web scraping |\n"
        "| III | Username recon, Image EXIF, Email OSINT |\n"
        "| IV  | Deep Search via LeakOSINT breach databases |\n\n"
        "### Auth\n"
        "Protected routes require `Authorization: Bearer <firebase-id-token>`.\n\n"
        "### Rate Limiting\n"
        "Apply Kong/Nginx upstream. No built-in limiting in this layer."
    ),
    contact={"name": "NexusScope Security Team", "url": "https://github.com/Harsh127-pixel/NexusScope"},
    license_info={"name": "MIT"},
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Router registration ───────────────────────────────────────────────────────
#  Unified investigations (create + poll any module)
app.include_router(investigations_router, prefix="/api/v1",           tags=["Investigations"])
#  Theater-specific direct access
app.include_router(theater1_router,       prefix="/api/v1/theater1",  tags=["Theater I — Dark Web"])
app.include_router(theater2_router,       prefix="/api/v1/theater2",  tags=["Theater II — Recon"])
app.include_router(theater3_router,       prefix="/api/v1/theater3",  tags=["Theater III — Identity"])
app.include_router(theater4_router,       prefix="/api/v1/deepsearch",tags=["Theater IV — Deep Search"])
#  Chatbot
app.include_router(bot_router,            prefix="/api/v1/chatbot",   tags=["Chatbot — Telegram"])
#  Legacy single-shot OSINT (pre-theater endpoints with DB logging)
app.include_router(intel_router,          prefix="/api/v1/intel",     tags=["Legacy OSINT Intel"])
#  S3 bucket leak hunting
app.include_router(s3_router,             prefix="/api/v1/scan",      tags=["S3 Leak Hunting"])


# ── Health endpoints ──────────────────────────────────────────────────────────
@app.get("/", response_model=HealthResponse, tags=["Health"], summary="Service health check")
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy", service=APP_NAME, version=APP_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/health", response_model=HealthResponse, tags=["Health"], summary="Detailed health check")
async def detailed_health() -> HealthResponse:
    from app.core.database import get_db_pool
    from app.core.firebase import get_firebase_app
    db_ok  = get_db_pool() is not None
    fb_ok  = get_firebase_app() is not None
    overall = "healthy" if db_ok and fb_ok else "degraded"
    return HealthResponse(
        status=f"{overall} | db={'connected' if db_ok else 'unavailable'} | firebase={'connected' if fb_ok else 'unavailable'}",
        service=APP_NAME, version=APP_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ── Lifecycle ─────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup() -> None:
    logger.info("=" * 60)
    logger.info("  %s  v%s  —  Starting up", APP_NAME, APP_VERSION)
    logger.info("=" * 60)
    init_firebase()
    await init_db()
    try:
        await initialize_pool()      # S3 hunting pool
        logger.info("S3 hunting DB pool ready.")
    except Exception as exc:
        logger.error("S3 hunting DB init FAILED: %s", exc)
    logger.info("Startup complete — API ready.")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await close_db()
    try:
        await close_pool()
    except Exception as exc:
        logger.error("S3 pool close error: %s", exc)
    logger.info("%s shutdown complete.", APP_NAME)


# ── Entrypoint ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=API_HOST, port=API_PORT, reload=True, log_level="info")
