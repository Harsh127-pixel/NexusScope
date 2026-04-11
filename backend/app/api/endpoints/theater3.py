import io
import time
import re
import logging
import httpx
import exifread
import asyncio
from typing import Any, Dict, Optional, List
from bs4 import BeautifulSoup
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.core.state import TASKS, TASK_LOCK
from app.core.investigation_tasks import _httpx_client, _pick_user_agent, _normalize_url

router = APIRouter()
logger = logging.getLogger(__name__)

class IdentityRequest(BaseModel):
    target: str
    options: Dict[str, Any] = Field(default_factory=dict)

@router.post("/username")
async def start_username_recon(payload: IdentityRequest):
    return await _create_task("username", payload)

@router.post("/metadata")
async def start_metadata_scan(payload: IdentityRequest):
    return await _create_task("metadata", payload)

async def _create_task(module: str, payload: IdentityRequest):
    import uuid, time
    task_id = str(uuid.uuid4())
    async with TASK_LOCK:
        TASKS[task_id] = {
            "id": task_id, "module": module, "target": payload.target, 
            "status": "queued", "created_at": time.time(), "options": payload.options, "result": None
        }
    return {"task_id": task_id}

async def _image_metadata(image_url: str, proxy: Optional[str], timeout: int) -> Dict[str, Any]:
    target = _normalize_url(image_url)
    try:
        async with _httpx_client(proxy=proxy, timeout=timeout) as client:
            resp = await client.get(target)
            raw = resp.content
    except Exception as e: return {"image_url": target, "error": str(e)}
    tags = {}
    try: tags = exifread.process_file(io.BytesIO(raw), details=False) or {}
    except: pass
    return {"image_url": target, "camera_make": str(tags.get("Image Make")) if tags.get("Image Make") else None}

async def _username_lookup(username: str, proxy: Optional[str], timeout: int) -> Dict[str, Any]:
    async def _check_github():
        url = f"https://github.com/{username}"
        try:
            async with _httpx_client(proxy=proxy, timeout=timeout) as client:
                resp = await client.get(url)
                return {"platform": "GitHub", "profile_found": resp.status_code == 200, "url": url}
        except: return {"platform": "GitHub"}
    results = await asyncio.gather(_check_github())
    return {"username": username, "profiles": list(results)}

async def _email_lookup(email: str) -> Dict[str, Any]:
    return {"email": email}
