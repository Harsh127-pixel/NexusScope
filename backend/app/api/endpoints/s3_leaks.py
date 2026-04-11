"""
app/api/endpoints/s3_leaks.py — S3 bucket leak hunting endpoints
Extracted from main.py §14.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.firebase import verify_firebase_token

# S3 workers / DB helpers live in the root-level modules
from database import get_scan
from workers import run_leak_scan

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Auth dependency ───────────────────────────────────────────────────────────

async def optional_auth(request: Request) -> Optional[Dict[str, Any]]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return verify_firebase_token(auth_header.split(" ", 1)[1])
    return None


# ── Pydantic models ───────────────────────────────────────────────────────────

class S3LeakScanRequest(BaseModel):
    domain: str = Field(..., example="example.com")


class S3BucketFinding(BaseModel):
    bucket_name: str
    http_code: int


class S3ScanResults(BaseModel):
    domain: str
    base_name: str
    total_checked: int
    buckets_found: Dict[str, List[S3BucketFinding]]
    errors: Dict[str, List[str]] = Field(default_factory=dict)


class S3ScanStatusResponse(BaseModel):
    task_id: str
    target_domain: str
    status: str = Field(..., pattern="^(running|completed|failed)$")
    results: Optional[S3ScanResults] = None
    error: Optional[str] = None


class S3ScanInitResponse(BaseModel):
    task_id: str
    message: str
    estimated_duration_seconds: int = 60


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/leaks",
    response_model=S3ScanInitResponse,
    tags=["S3 Leak Hunting"],
    summary="Start an S3 bucket leak scan",
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_s3_leak_scan(
    request: S3LeakScanRequest,
    background_tasks: BackgroundTasks,
    user: Optional[Dict[str, Any]] = Depends(optional_auth),
) -> S3ScanInitResponse:
    """
    Initiates an async scan for exposed S3 buckets associated with the target domain.
    Poll `/api/v1/scan/{task_id}` for results.
    """
    task_id = uuid.uuid4()
    logger.info(
        "S3 scan initiated: task_id=%s domain=%s user=%s",
        task_id, request.domain,
        user.get("email") if user else "anonymous"
    )
    background_tasks.add_task(run_leak_scan, task_id, request.domain)
    return S3ScanInitResponse(
        task_id=str(task_id),
        message="Scan started. Poll /api/v1/scan/{task_id} for results.",
        estimated_duration_seconds=60,
    )


@router.get(
    "/{task_id}",
    response_model=S3ScanStatusResponse,
    tags=["S3 Leak Hunting"],
    summary="Poll S3 leak scan status",
)
async def get_s3_scan_status(
    task_id: str,
    user: Optional[Dict[str, Any]] = Depends(optional_auth),
) -> S3ScanStatusResponse:
    """Returns the current status and results of an S3 leak scan."""
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid UUID: {task_id}")

    try:
        record = await get_scan(task_uuid)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable.")

    if record is None:
        raise HTTPException(status_code=404, detail=f"Scan not found: {task_id}")

    status_val = record["status"]
    results = None
    error = None

    if status_val == "completed":
        raw = record["results"] or {}
        if isinstance(raw, str):
            raw = json.loads(raw)
        results = S3ScanResults(**raw)
    elif status_val == "failed":
        raw = record["results"] or {}
        if isinstance(raw, str):
            raw = json.loads(raw)
        error = raw.get("error", "Unknown error")

    return S3ScanStatusResponse(
        task_id=str(task_uuid),
        target_domain=record["target_domain"],
        status=status_val,
        results=results,
        error=error,
    )
