import os
import re
import logging
import httpx
from typing import Any, Dict, Optional
from bs4 import BeautifulSoup
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.core.state import TASKS, TASK_LOCK
from app.core.investigation_tasks import _httpx_client, _pick_user_agent

router = APIRouter()
logger = logging.getLogger(__name__)

class DarkWebRequest(BaseModel):
    target: str
    options: Dict[str, Any] = Field(default_factory=dict)

@router.post("/darkweb")
async def start_darkweb_scan(payload: DarkWebRequest):
    import uuid
    import time
    task_id = str(uuid.uuid4())
    async with TASK_LOCK:
        TASKS[task_id] = {
            "id": task_id,
            "module": "darkweb",
            "target": payload.target,
            "status": "queued",
            "created_at": time.time(),
            "options": payload.options,
            "result": None
        }
    return {"task_id": task_id}

TOR_PROXY_URL = os.getenv("TOR_PROXY_URL", "socks5://16.16.25.208:9050")
TOR_TIMEOUT = int(os.getenv("TOR_TIMEOUT", "45"))

async def _check_tor_health() -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(proxy=TOR_PROXY_URL, timeout=10.0) as client:
            resp = await client.get("https://check.torproject.org/", follow_redirects=True)
            if "Congratulations" in resp.text:
                soup = BeautifulSoup(resp.text, "lxml")
                ip_tag = soup.find("strong")
                return {"tor_running": True, "exit_ip": ip_tag.get_text(strip=True) if ip_tag else "Unknown", "proxy_url": TOR_PROXY_URL, "status": "connected"}
            return {"tor_running": False, "proxy_url": TOR_PROXY_URL, "status": "connected"}
    except Exception as exc:
        return {"tor_running": False, "status": "error", "error": str(exc)}

async def _ahmia_search(query: str) -> Dict[str, Any]:
    url = f"https://ahmia.fi/search/?q={query}"
    try:
        async with _httpx_client(proxy=None, timeout=20) as client:
            response = await client.get(url, follow_redirects=True)
            html = response.text
    except Exception as exc:
        return {"is_search": True, "query": query, "url": url, "error": f"Ahmia search failed: {str(exc)}"}
    soup = BeautifulSoup(html, "lxml")
    results = []
    for item in soup.find_all("li"):
        cite_tag = item.find("cite")
        if not cite_tag: continue
        title_tag = item.find("h4") or item.find("a")
        desc_tag = item.find("p")
        onion_url = cite_tag.get_text(strip=True)
        if onion_url:
            results.append({"title": title_tag.get_text(strip=True) if title_tag else "Unknown", "onion_url": onion_url, "description": desc_tag.get_text(strip=True) if desc_tag else ""})
    return {"is_search": True, "url": url, "query": query, "search_results": results[:25], "total_returned": len(results), "source": "Ahmia.fi Search Index"}

async def _onion_crawler(onion_url: str) -> Dict[str, Any]:
    if ".onion" not in onion_url and "http" not in onion_url: return await _ahmia_search(onion_url)
    if not onion_url.startswith("http"): onion_url = f"http://{onion_url}"
    tor_status = await _check_tor_health()
    if not tor_status["tor_running"]: return {"url": onion_url, "crawl_success": False, "tor_status": tor_status, "error": f"Tor proxy unreachable"}
    try:
        async with httpx.AsyncClient(proxy=TOR_PROXY_URL, timeout=TOR_TIMEOUT, headers={"User-Agent": _pick_user_agent()}, follow_redirects=True, verify=False) as client:
            response = await client.get(onion_url)
            html = response.text
    except Exception as exc: return {"url": onion_url, "crawl_success": False, "error": str(exc)}
    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else None
    for tag in soup(["script", "style", "noscript"]): tag.decompose()
    text_excerpt = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()[:1500]
    onion_links = list(set(re.findall(r"[a-z2-7]{16,56}\.onion", html.lower())))
    emails_found = list(set(re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", html)))[:20]
    return {"url": onion_url, "crawl_success": True, "title": title, "text_excerpt": text_excerpt, "onion_links_discovered": onion_links[:50], "emails_found": emails_found}
