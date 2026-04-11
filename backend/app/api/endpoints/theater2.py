import asyncio
import logging
import socket
import ssl
import re
import httpx
import dns.asyncresolver
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.core.state import TASKS, TASK_LOCK
from app.core.investigation_tasks import _httpx_client, _pick_user_agent, _normalize_url

router = APIRouter()
logger = logging.getLogger(__name__)

class ReconRequest(BaseModel):
    target: str
    options: Dict[str, Any] = Field(default_factory=dict)

@router.post("/ip")
async def start_ip_intel(payload: ReconRequest):
    return await _create_task("ip", payload)

@router.post("/domain")
async def start_domain_intel(payload: ReconRequest):
    return await _create_task("domain", payload)

async def _create_task(module: str, payload: ReconRequest):
    import uuid, time
    task_id = str(uuid.uuid4())
    async with TASK_LOCK:
        TASKS[task_id] = {
            "id": task_id, "module": module, "target": payload.target, 
            "status": "queued", "created_at": time.time(), "options": payload.options, "result": None
        }
    return {"task_id": task_id}

# ── LOGIC ──────────────────────────────────────────────────────────
def _extract_domain_host(domain: str) -> str:
    value = domain.strip().lower()
    if not value: return value
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.hostname or value

def _whois_server_for_tld(domain: str) -> str:
    tld = domain.rsplit('.', 1)[-1].lower()
    return {'com': 'whois.verisign-grs.com','net': 'whois.verisign-grs.com'}.get(tld, 'whois.iana.org')

async def _whois_lookup(domain: str) -> Dict[str, Any]:
    host = _extract_domain_host(domain)
    server = _whois_server_for_tld(host)
    def _lookup():
        try:
            with socket.create_connection((server, 43), timeout=10) as conn:
                conn.sendall((host + "\r\n").encode("utf-8"))
                raw = conn.recv(10000).decode("utf-8", errors="replace")
            return {"whois_server": server, "raw": raw[:2000]}
        except: return {"error": "WHOIS failed"}
    return await asyncio.get_running_loop().run_in_executor(None, _lookup)

async def _domain_lookup(domain: str) -> Dict[str, Any]:
    resolver = dns.asyncresolver.Resolver()
    records = {}
    for rt in ["A", "MX", "NS"]:
        try:
            answer = await resolver.resolve(domain, rt)
            records[rt] = [str(r) for r in answer]
        except: records[rt] = []
    return {"domain": domain, "records": records, "whois": await _whois_lookup(domain)}

async def _ip_lookup(ip: str) -> Dict[str, Any]:
    result = {"ip": ip, "hostname": "resolving..."}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(f"https://ipapi.co/{ip}/json/")
            if resp.status_code == 200: result.update(resp.json())
    except: pass
    return result

async def _scrape_web(target: str, proxy: Optional[str], timeout: int, use_playwright: bool) -> Dict[str, Any]:
    url = _normalize_url(target)
    html = None
    if use_playwright:
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                page = await browser.new_page(user_agent=_pick_user_agent())
                await page.goto(url, wait_until="networkidle", timeout=timeout*1000)
                html = await page.content()
                await browser.close()
        except: pass
    if not html:
        async with _httpx_client(proxy=proxy, timeout=timeout) as client:
            resp = await client.get(url)
            html = resp.text
    soup = BeautifulSoup(html, "lxml")
    return {"url": url, "title": soup.title.get_text(strip=True) if soup.title else None}

async def _phone_lookup(phone: str) -> Dict[str, Any]:
    return {"phone": phone, "note": "Phone lookup module integrated."}
