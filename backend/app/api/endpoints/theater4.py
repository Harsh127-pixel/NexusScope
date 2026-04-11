"""
╔══════════════════════════════════════════════════════════════════════════════╗
║              NexusScope — Theater IV: Deep Search (LeakOSINT API)            ║
║     Powered by leakosintapi.com — Breach DB, PII, and Dark Intelligence      ║
╚══════════════════════════════════════════════════════════════════════════════╝

CAPABILITIES
────────────
  ✓  Email breach lookup across thousands of databases
  ✓  Phone number reverse intelligence
  ✓  IP address threat actor correlation
  ✓  Full name PII discovery
  ✓  Domain / organization data leaks

ENDPOINT
────────
  POST /api/v1/deepsearch/search   — initiate a deep search task
  GET  /api/v1/deepsearch/raw      — direct passthrough for custom queries
"""

import os
import re
import math
import logging
import uuid
import time
import httpx
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.core.state import TASKS, TASK_LOCK

router = APIRouter()
logger = logging.getLogger(__name__)

# ── LeakOSINT Config ─────────────────────────────────────────────────────────
LEAKOSINT_API_URL = os.getenv("LEAKOSINT_API_URL", "https://leakosintapi.com/")
LEAKOSINT_TOKEN   = os.getenv("LEAKOSINT_TOKEN", "1900800372:36uned3K")
LEAKOSINT_LANG    = os.getenv("LEAKOSINT_LANG", "en")
LEAKOSINT_LIMIT   = int(os.getenv("LEAKOSINT_LIMIT", "100"))


# ── Pydantic Models ───────────────────────────────────────────────────────────
class DeepSearchRequest(BaseModel):
    target: str = Field(..., description="Query: email, IP, phone, name, or domain")
    limit: int  = Field(100, ge=100, le=10000, description="Result limit (100–10,000)")
    lang: str   = Field("en", description="Language code for results (en, ru, etc.)")

class DeepSearchRawRequest(BaseModel):
    request: Union[str, List[str]] = Field(..., description="Raw query or list of queries")
    limit: int  = Field(100, ge=100, le=10000)
    lang: str   = Field("en")


# ── Query Type Classifier ─────────────────────────────────────────────────────
def _classify_target(target: str) -> str:
    """Infer the data type of the query target."""
    t = target.strip()
    if re.match(r"^[\w.+-]+@[\w-]+\.[a-z]{2,}$", t, re.I):
        return "email"
    if re.match(r"^\+?\d[\d\s\-\(\)]{7,14}$", t):
        return "phone"
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", t):
        return "ip"
    if re.match(r"^(https?://)?[\w.-]+\.[a-z]{2,}(/.*)?$", t, re.I) and " " not in t:
        return "domain"
    return "name"


# ── Price Calculator ──────────────────────────────────────────────────────────
def _calculate_price(query: str, limit: int) -> float:
    """
    Calculates estimated cost per LeakOSINT pricing formula:
    price = 0.0002 * (5 + sqrt(limit * complexity))
    """
    # Strip non-word tokens (dates, short tokens)
    tokens = [
        w for w in re.split(r"\s+", query.strip())
        if len(w) >= 4 and not re.match(r"^\d{1,5}$", w) and not re.match(r"\d{4}-\d{2}-\d{2}", w)
    ]
    n = len(tokens)
    if n <= 1:   complexity = 1
    elif n == 2: complexity = 5
    elif n == 3: complexity = 16
    else:        complexity = 40

    return round(0.0002 * (5 + math.sqrt(limit * complexity)), 6)


# ── Core API Call ─────────────────────────────────────────────────────────────
async def _call_leakosint(
    request: Union[str, List[str]],
    limit: int = LEAKOSINT_LIMIT,
    lang: str = LEAKOSINT_LANG,
) -> Dict[str, Any]:
    """
    Makes the POST request to leakosintapi.com and returns parsed results.
    """
    payload = {
        "token": LEAKOSINT_TOKEN,
        "request": request,
        "limit": limit,
        "lang": lang,
        "type": "json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(LEAKOSINT_API_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

    if "Error code" in data:
        raise HTTPException(
            status_code=502,
            detail=f"LeakOSINT API Error: {data['Error code']}"
        )

    return data


# ── Result Formatter ──────────────────────────────────────────────────────────
def _format_results(raw: Dict[str, Any], query: str, limit: int) -> Dict[str, Any]:
    """Transforms raw LeakOSINT response into a structured NexusScope result."""
    query_type = _classify_target(query if isinstance(query, str) else query[0])
    price       = _calculate_price(query if isinstance(query, str) else " ".join(query), limit)

    databases = []
    total_records = 0

    for db_name, db_data in raw.get("List", {}).items():
        is_empty = db_name == "No results found"
        records  = db_data.get("Data", []) if not is_empty else []
        total_records += len(records)

        databases.append({
            "database": db_name,
            "info":     db_data.get("InfoLeak", ""),
            "records":  records[:50],  # cap per-DB to 50 for readability
            "count":    len(records),
            "has_data": not is_empty and len(records) > 0,
        })

    # Sort: hits first, empty last
    databases.sort(key=lambda d: d["has_data"], reverse=True)

    return {
        "module":        "deepsearch",
        "query":         query,
        "query_type":    query_type,
        "limit":         limit,
        "total_records": total_records,
        "databases_hit": sum(1 for d in databases if d["has_data"]),
        "estimated_cost_usd": price,
        "databases":     databases,
    }


# ── Background Task ───────────────────────────────────────────────────────────
async def _run_deepsearch(task_id: str, query: str, limit: int, lang: str):
    """Background worker for deep search tasks."""
    task = TASKS[task_id]
    task["status"] = "processing"

    try:
        raw    = await _call_leakosint(query, limit, lang)
        result = _format_results(raw, query, limit)
        task["status"] = "completed"
        task["result"] = result
        logger.info("DeepSearch task %s completed — %d records found", task_id, result["total_records"])
    except Exception as exc:
        task["status"] = "failed"
        task["error"]  = str(exc)
        logger.error("DeepSearch task %s failed: %s", task_id, exc)


# ── API Endpoints ─────────────────────────────────────────────────────────────

@router.post(
    "/search",
    summary="Launch a Deep Search investigation",
    response_description="Returns a task_id for polling.",
    tags=["Theater IV — Deep Search"],
)
async def start_deepsearch(
    payload: DeepSearchRequest,
    background_tasks: BackgroundTasks,
):
    """
    ## Deep Search

    Searches **thousands of breach databases** for any trace of your target.

    ### Supported target types (auto-detected)
    | Type   | Example                |
    |--------|------------------------|
    | Email  | `user@example.com`     |
    | Phone  | `+1-555-867-5309`      |
    | IP     | `192.168.1.1`          |
    | Name   | `Elon Reeve Musk`      |
    | Domain | `example.com`          |

    Returns a `task_id`. Poll `/api/v1/investigations/{task_id}` for results.
    """
    task_id = str(uuid.uuid4())

    async with TASK_LOCK:
        TASKS[task_id] = {
            "id":         task_id,
            "module":     "deepsearch",
            "target":     payload.target,
            "status":     "queued",
            "created_at": time.time(),
            "result":     None,
            "error":      None,
            "options":    {"limit": payload.limit, "lang": payload.lang},
        }

    background_tasks.add_task(
        _run_deepsearch, task_id, payload.target, payload.limit, payload.lang
    )
    return {"task_id": task_id, "estimated_cost_usd": _calculate_price(payload.target, payload.limit)}


@router.post(
    "/raw",
    summary="Direct LeakOSINT API passthrough",
    tags=["Theater IV — Deep Search"],
)
async def deepsearch_raw(payload: DeepSearchRawRequest):
    """
    ## Raw Deep Search

    Direct passthrough to LeakOSINT API. Use when you want:
    - Multiple queries in one request (array of strings)
    - Custom language / limit per call
    - Immediate (synchronous) results without polling

    **Rate limit:** 3 requests / second / IP.
    """
    raw = await _call_leakosint(payload.request, payload.limit, payload.lang)
    query_str = payload.request if isinstance(payload.request, str) else "\n".join(payload.request)
    return _format_results(raw, query_str, payload.limit)
