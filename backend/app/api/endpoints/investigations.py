import asyncio
import io
import json
import os
import random
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from celery import Celery
from celery.result import AsyncResult
import dns.asyncresolver
import exifread
import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

TASKS: Dict[str, Dict[str, Any]] = {}
TASK_LOCK = asyncio.Lock()
UA_FILE_PATH = Path(__file__).resolve().parents[2] / "data" / "user_agents.json"
_CACHED_UA: Optional[List[str]] = None
DEFAULT_SCRAPER_PROXY = os.getenv("DEFAULT_SCRAPER_PROXY")

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://localhost:6379/0"))
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)

celery_app = Celery(
    "nexus_backend",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

WORKER_TASK_MAP = {
    "domain": "tasks.perform_dns_lookup",
    "scraper": "tasks.scrape_web_intelligence",
    "metadata": "tasks.analyze_image_metadata",
}


class InvestigationRequest(BaseModel):
    target: str
    module: Optional[str] = None
    type: Optional[str] = None
    proxy: Optional[str] = None
    options: Dict[str, Any] = Field(default_factory=dict)


class CreateInvestigationResponse(BaseModel):
    task_id: str


class InvestigationStatusResponse(BaseModel):
    task_id: str
    module: str
    target: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


def _map_celery_state(state: str) -> str:
    normalized = (state or "").upper()
    if normalized == "SUCCESS":
        return "completed"
    if normalized in {"STARTED", "RETRY", "RECEIVED"}:
        return "processing"
    if normalized == "FAILURE":
        return "failed"
    return "queued"


def _normalize_url(target: str) -> str:
    parsed = urlparse(target)
    if not parsed.scheme:
        return f"https://{target}"
    return target


def _load_user_agents() -> List[str]:
    global _CACHED_UA
    if _CACHED_UA is not None:
        return _CACHED_UA

    if UA_FILE_PATH.exists():
        with UA_FILE_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list) and data:
                _CACHED_UA = [str(item) for item in data]
                return _CACHED_UA

    _CACHED_UA = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ]
    return _CACHED_UA


def _pick_user_agent() -> str:
    return random.choice(_load_user_agents())


def _httpx_client(proxy: Optional[str], timeout: int) -> httpx.AsyncClient:
    kwargs: Dict[str, Any] = {
        "timeout": timeout,
        "follow_redirects": True,
        "headers": {
            "User-Agent": _pick_user_agent(),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }
    if proxy:
        kwargs["proxy"] = proxy
    return httpx.AsyncClient(**kwargs)


async def _domain_lookup(domain: str) -> Dict[str, Any]:
    resolver = dns.asyncresolver.Resolver()
    record_types = ["A", "MX", "TXT", "NS", "AAAA", "CNAME"]
    records: Dict[str, Any] = {}

    for record_type in record_types:
        try:
            answer = await resolver.resolve(domain, record_type)
            if record_type == "TXT":
                records[record_type] = [
                    " ".join(
                        piece.decode("utf-8", errors="replace") if isinstance(piece, bytes) else str(piece)
                        for piece in row.strings
                    )
                    for row in answer
                ]
            else:
                records[record_type] = [str(row) for row in answer]
        except Exception as exc:
            records[record_type] = f"lookup_error: {exc}"

    return {
        "domain": domain,
        "records": records,
        "source": "dns_asyncresolver",
    }


async def _ip_lookup(ip_addr: str) -> Dict[str, Any]:
    resolver = dns.asyncresolver.Resolver()
    ptr_result: List[str] = []
    try:
        answer = await resolver.resolve_address(ip_addr)
        ptr_result = [str(item) for item in answer]
    except Exception as exc:
        ptr_result = [f"ptr_error: {exc}"]

    return {
        "ip": ip_addr,
        "ptr": ptr_result,
        "note": "External geolocation API is disabled in scraper-only mode.",
    }


async def _scrape_web(target: str, proxy: Optional[str], timeout: int, use_playwright: bool) -> Dict[str, Any]:
    url = _normalize_url(target)
    html: Optional[str] = None
    method = "httpx"

    if use_playwright:
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=_pick_user_agent())
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
                html = await page.content()
                await browser.close()
                method = "playwright"
        except Exception:
            html = None

    if html is None:
        async with _httpx_client(proxy=proxy, timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text

    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else None
    meta_description = soup.find("meta", attrs={"name": re.compile("description", re.I)})
    links = [
        a.get("href") for a in soup.find_all("a", href=True)[:20]
    ]

    return {
        "url": url,
        "fetch_method": method,
        "title": title,
        "meta_description": meta_description.get("content") if meta_description else None,
        "h1": [h.get_text(strip=True) for h in soup.find_all("h1")[:5]],
        "links_sample": links,
    }


async def _username_lookup(username: str, proxy: Optional[str], timeout: int) -> Dict[str, Any]:
    url = f"https://github.com/{username}"
    async with _httpx_client(proxy=proxy, timeout=timeout) as client:
        response = await client.get(url)

    if response.status_code == 404:
        return {
            "platform": "github",
            "username": username,
            "profile_found": False,
            "url": url,
        }

    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    name_tag = soup.find("span", {"itemprop": "name"})
    bio_tag = soup.find("div", class_=re.compile(r"p-note", re.I))

    return {
        "platform": "github",
        "username": username,
        "profile_found": True,
        "url": url,
        "display_name": name_tag.get_text(strip=True) if name_tag else None,
        "bio": bio_tag.get_text(strip=True) if bio_tag else None,
    }


async def _image_metadata(image_url: str, proxy: Optional[str], timeout: int) -> Dict[str, Any]:
    target = _normalize_url(image_url)
    async with _httpx_client(proxy=proxy, timeout=timeout) as client:
        response = await client.get(target)
        response.raise_for_status()
        raw = response.content

    tags = exifread.process_file(io.BytesIO(raw), details=False)

    return {
        "image_url": target,
        "tag_count": len(tags),
        "camera_make": str(tags.get("Image Make")) if tags.get("Image Make") else None,
        "camera_model": str(tags.get("Image Model")) if tags.get("Image Model") else None,
        "datetime_original": str(tags.get("EXIF DateTimeOriginal")) if tags.get("EXIF DateTimeOriginal") else None,
    }


async def _execute_task(task_id: str) -> None:
    async with TASK_LOCK:
        task = TASKS[task_id]
        task["status"] = "processing"

    start = time.time()
    module = str(task["module"])
    target = str(task["target"])
    options = task.get("options", {}) or {}
    proxy = task.get("proxy")
    timeout = int(options.get("timeout", 12))
    use_playwright = bool(options.get("use_playwright", False))

    try:
        if module == "domain":
            result = await _domain_lookup(target)
        elif module == "ip":
            result = await _ip_lookup(target)
        elif module == "username":
            result = await _username_lookup(target, proxy=proxy, timeout=timeout)
        elif module == "metadata":
            result = await _image_metadata(target, proxy=proxy, timeout=timeout)
        elif module == "geolocation":
            result = {
                "target": target,
                "note": "Geolocation by external API is disabled. Use module=scraper with a map/listing page URL for location hints.",
            }
        elif module == "scraper":
            result = await _scrape_web(target, proxy=proxy, timeout=timeout, use_playwright=use_playwright)
        else:
            raise ValueError(f"Unsupported module: {module}")

        completed_at = time.time()
        async with TASK_LOCK:
            task["status"] = "completed"
            task["result"] = result
            task["completed_at"] = completed_at
            task["duration_ms"] = int((completed_at - start) * 1000)
    except Exception as exc:
        completed_at = time.time()
        async with TASK_LOCK:
            task["status"] = "failed"
            task["error"] = str(exc)
            task["completed_at"] = completed_at
            task["duration_ms"] = int((completed_at - start) * 1000)


@router.post("/investigations", response_model=CreateInvestigationResponse)
async def create_investigation(payload: InvestigationRequest) -> CreateInvestigationResponse:
    module = (payload.module or payload.type or "").strip().lower()
    if not module:
        raise HTTPException(status_code=422, detail="Either 'module' or 'type' is required.")

    task_id = str(uuid.uuid4())
    task = {
        "task_id": task_id,
        "module": module,
        "target": payload.target,
        "status": "queued",
        "result": None,
        "error": None,
        "created_at": time.time(),
        "completed_at": None,
        "duration_ms": None,
        "options": payload.options,
        "proxy": payload.proxy or payload.options.get("proxy") or DEFAULT_SCRAPER_PROXY,
        "execution_mode": "worker" if module in WORKER_TASK_MAP else "local",
    }

    async with TASK_LOCK:
        TASKS[task_id] = task

    if module in WORKER_TASK_MAP:
        celery_task_name = WORKER_TASK_MAP[module]
        celery_app.send_task(celery_task_name, args=[payload.target], task_id=task_id)
    else:
        asyncio.create_task(_execute_task(task_id))

    return CreateInvestigationResponse(task_id=task_id)


@router.get("/investigations/{task_id}", response_model=InvestigationStatusResponse)
async def get_investigation_status(task_id: str) -> InvestigationStatusResponse:
    async with TASK_LOCK:
        task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Investigation not found")

    if task.get("execution_mode") == "worker":
        async_result = AsyncResult(task_id, app=celery_app)
        status = _map_celery_state(async_result.state)

        if status == "completed":
            result_payload = async_result.result if isinstance(async_result.result, dict) else {"result": async_result.result}
            async with TASK_LOCK:
                task["status"] = status
                task["result"] = result_payload
                task["error"] = None
            result = result_payload
            error = None
        elif status == "failed":
            error_message = str(async_result.result)
            async with TASK_LOCK:
                task["status"] = status
                task["error"] = error_message
            result = None
            error = error_message
        else:
            async with TASK_LOCK:
                task["status"] = status
            result = None
            error = None
    else:
        result = task["result"]
        error = task["error"]

    return InvestigationStatusResponse(
        task_id=task["task_id"],
        module=task["module"],
        target=task["target"],
        status=task["status"],
        result=result,
        error=error,
    )


@router.get("/history")
async def get_history(
    search: Optional[str] = None,
    module: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 25,
) -> Dict[str, Any]:
    async with TASK_LOCK:
        tasks = list(TASKS.values())

    if search:
        q = search.lower()
        tasks = [
            t for t in tasks
            if q in t["task_id"].lower() or q in str(t["target"]).lower()
        ]
    if module:
        tasks = [t for t in tasks if t["module"] == module.lower()]
    if status:
        tasks = [t for t in tasks if t["status"] == status.lower()]

    tasks.sort(key=lambda t: t["created_at"], reverse=True)
    total = len(tasks)
    start = max(page - 1, 0) * limit
    end = start + limit

    return {
        "tasks": [
            {
                "task_id": t["task_id"],
                "module": t["module"],
                "target": t["target"],
                "status": t["status"],
                "result": t["result"],
                "error": t["error"],
                "created_at": t["created_at"],
                "completed_at": t["completed_at"],
                "duration_ms": t["duration_ms"],
            }
            for t in tasks[start:end]
        ],
        "total": total,
    }


@router.delete("/investigations/{task_id}")
async def delete_investigation(task_id: str) -> Dict[str, str]:
    async with TASK_LOCK:
        if task_id not in TASKS:
            raise HTTPException(status_code=404, detail="Investigation not found")
        del TASKS[task_id]
    return {"status": "deleted"}
