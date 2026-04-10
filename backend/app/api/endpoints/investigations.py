import asyncio
import logging
import hashlib
import io
import json
import os
import random
import re
import time
import uuid
import socket
import ssl
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from datetime import datetime, timezone

import dns.asyncresolver
from dotenv import load_dotenv
import exifread
import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / ".env", override=False)

TASKS: Dict[str, Dict[str, Any]] = {}
TASK_LOCK = asyncio.Lock()
UA_FILE_PATH = Path(__file__).resolve().parents[2] / "data" / "user_agents.json"
_CACHED_UA: Optional[List[str]] = None
DEFAULT_SCRAPER_PROXY = os.getenv("DEFAULT_SCRAPER_PROXY")

# ── Theater 1: Dark Web / Onion ───────────────────────────────
TOR_PROXY_URL = os.getenv("TOR_PROXY_URL", "socks5://127.0.0.1:9050")
TOR_TIMEOUT = int(os.getenv("TOR_TIMEOUT", "30"))

# ── Theater 2: General Recon (Phone) ─────────────────────────
NUMVERIFY_API_KEY = os.getenv("NUMVERIFY_API_KEY", "")

# ── Theater 3: Identity & Credential Hunting ──────────────────
HIBP_API_KEY = os.getenv("HIBP_API_KEY", "")


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


def _normalize_module_name(module_raw: str) -> str:
    """Map user-facing module labels/aliases to canonical internal module keys."""
    value = module_raw.strip().lower()
    collapsed = re.sub(r"[\s_-]+", "", value)

    alias_map = {
        # ── Existing modules ───────────────────────────────────────
        "domain": "domain",
        "domains": "domain",
        "ip": "ip",
        "iplookup": "ip",
        "username": "username",
        "user": "username",
        "metadata": "metadata",
        "image": "metadata",
        "imagemetadata": "metadata",
        "geolocation": "geolocation",
        "geo": "geolocation",
        "scraper": "scraper",
        "webscraper": "scraper",
        "webscan": "scraper",
        "crawl": "scraper",
        # ── Theater 1: Dark Web / Onion ────────────────────────────
        "darkweb": "darkweb",
        "onion": "darkweb",
        "tor": "darkweb",
        "torcrawl": "darkweb",
        "onioncrawler": "darkweb",
        # ── Theater 2: General Recon ───────────────────────────────
        "phone": "phone",
        "mobile": "phone",
        "phonelookup": "phone",
        "skiptrace": "phone",
        # ── Theater 3: Identity & Credential Hunting ───────────────
        "email": "email",
        "emailhunt": "email",
        "hibp": "email",
        "breach": "email",
        "credential": "email",
    }
    return alias_map.get(collapsed, value)


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


def _extract_domain_host(domain: str) -> str:
    value = domain.strip().lower()
    if not value:
        return value
    parsed = urlparse(value if "://" in value else f"https://{value}")
    return parsed.hostname or value


def _whois_server_for_tld(domain: str) -> str:
    tld = domain.rsplit('.', 1)[-1].lower()
    return {
        'com': 'whois.verisign-grs.com',
        'net': 'whois.verisign-grs.com',
        'org': 'whois.pir.org',
        'io': 'whois.nic.io',
        'in': 'whois.registry.in',
        'co': 'whois.nic.co',
        'ai': 'whois.nic.ai',
    }.get(tld, 'whois.iana.org')


def _query_whois(server: str, query: str) -> str:
    with socket.create_connection((server, 43), timeout=10) as conn:
        conn.sendall((query + "\r\n").encode("utf-8"))
        chunks: List[bytes] = []
        while True:
            data = conn.recv(4096)
            if not data:
                break
            chunks.append(data)
    return b"".join(chunks).decode("utf-8", errors="replace")


def _parse_whois_field(text: str, patterns: List[str]) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()
    return None


def _parse_whois_dates(text: str) -> Dict[str, Optional[str]]:
    fields = {
        "creation_date": [r"Creation Date:\s*(.+)", r"Created On:\s*(.+)", r"Registered On:\s*(.+)"],
        "updated_date": [r"Updated Date:\s*(.+)", r"Registry Expiry Date:\s*(.+)"],
        "expiration_date": [r"Expiry Date:\s*(.+)", r"Registrar Registration Expiration Date:\s*(.+)"],
    }
    return {key: _parse_whois_field(text, value) for key, value in fields.items()}


async def _whois_lookup(domain: str) -> Dict[str, Any]:
    host = _extract_domain_host(domain)
    server = _whois_server_for_tld(host)
    loop = asyncio.get_running_loop()

    def _lookup() -> Dict[str, Any]:
        raw = _query_whois(server, host)
        referral = _parse_whois_field(raw, [r"Registrar WHOIS Server:\s*(.+)", r"Whois Server:\s*(.+)"])
        if referral and referral.lower() not in {server.lower(), 'none'}:
            raw = _query_whois(referral.strip(), host)
            server_name = referral.strip()
        else:
            server_name = server

        registrar = _parse_whois_field(raw, [r"Registrar:\s*(.+)", r"Sponsoring Registrar:\s*(.+)"])
        name_servers = re.findall(r"Name Server:\s*(.+)", raw, re.IGNORECASE)
        dates = _parse_whois_dates(raw)
        registry_domain_id = _parse_whois_field(raw, [r"Domain Name:\s*(.+)", r"Domain:\s*(.+)"])
        registrant_country = _parse_whois_field(raw, [r"Registrant Country:\s*(.+)"])
        registrant_state = _parse_whois_field(raw, [r"Registrant State/Province:\s*(.+)"])

        return {
            "whois_server": server_name,
            "registrar": registrar,
            "domain": registry_domain_id or host,
            "name_servers": list(dict.fromkeys(ns.strip().rstrip('.') for ns in name_servers if ns.strip())),
            "registrant_country": registrant_country,
            "registrant_state": registrant_state,
            **dates,
            "raw": raw[:12000],
        }

    return await loop.run_in_executor(None, _lookup)


def _normalize_record_values(record: Any) -> List[str]:
    if isinstance(record, list):
        return [str(item) for item in record]
    if record is None:
        return []
    return [str(record)]


async def _common_subdomains(domain: str) -> List[Dict[str, Any]]:
    candidates = [
        "www", "mail", "smtp", "mx", "ns1", "ns2", "api", "dev", "test", "staging",
        "admin", "portal", "vpn", "cdn", "secure", "shop", "app", "blog", "support", "status",
    ]
    resolver = dns.asyncresolver.Resolver()
    found: List[Dict[str, Any]] = []

    for prefix in candidates:
        host = f"{prefix}.{domain}"
        try:
            answer = await resolver.resolve(host, "A")
            found.append({"subdomain": host, "ips": [str(row) for row in answer]})
        except Exception:
            continue
    return found


async def _crtsh_subdomains(domain: str) -> List[Dict[str, Any]]:
    url = f"https://crt.sh/?q=%25.{domain}&output=json"
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": _pick_user_agent()}) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return []

    discovered: Dict[str, Dict[str, Any]] = {}
    for item in payload if isinstance(payload, list) else []:
        name_value = str(item.get("name_value", ""))
        for entry in name_value.splitlines():
            candidate = entry.strip().lstrip('*.')
            if candidate.endswith(domain):
                discovered.setdefault(candidate, {"subdomain": candidate, "sources": set(), "ips": []})["sources"].add("crt.sh")
    return [
        {"subdomain": key, "source": "crt.sh"}
        for key in sorted(discovered.keys())
    ]


async def _tls_metadata(domain: str) -> Dict[str, Any]:
    host = _extract_domain_host(domain)

    def _lookup() -> Dict[str, Any]:
        context = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as raw_socket:
            with context.wrap_socket(raw_socket, server_hostname=host) as secure_socket:
                certificate = secure_socket.getpeercert()
        san_values = [value for kind, value in certificate.get("subjectAltName", []) if kind.lower() == "dns"]
        return {
            "issuer": "/".join(f"{k}={v}" for k, v in certificate.get("issuer", [[("unknown", "unknown")]])[0]),
            "subject": "/".join(f"{k}={v}" for k, v in certificate.get("subject", [[("unknown", "unknown")]])[0]),
            "not_before": certificate.get("notBefore"),
            "not_after": certificate.get("notAfter"),
            "san": san_values,
            "tls_version": secure_socket.version(),
        }

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _lookup)


async def _web_fingerprint(domain: str) -> Dict[str, Any]:
    url = _normalize_url(domain)
    headers: Dict[str, str] = {}
    title: Optional[str] = None
    robots: Optional[str] = None
    sitemap: Optional[str] = None
    status_code: Optional[int] = None
    method = "httpx"

    try:
        async with _httpx_client(proxy=None, timeout=12) as client:
            response = await client.get(url)
            status_code = response.status_code
            headers = dict(response.headers)
            html = response.text
        soup = BeautifulSoup(html, "lxml")
        title = soup.title.get_text(strip=True) if soup.title else None
        try:
            async with _httpx_client(proxy=None, timeout=8) as client:
                robots_response = await client.get(f"{url.rstrip('/')}/robots.txt")
                if robots_response.status_code < 400:
                    robots = robots_response.text[:4000]
        except Exception:
            pass
        try:
            async with _httpx_client(proxy=None, timeout=8) as client:
                sitemap_response = await client.get(f"{url.rstrip('/')}/sitemap.xml")
                if sitemap_response.status_code < 400:
                    sitemap = sitemap_response.text[:4000]
        except Exception:
            pass
    except Exception:
        pass

    return {
        "url": url,
        "status_code": status_code,
        "server": headers.get("server"),
        "x_powered_by": headers.get("x-powered-by"),
        "content_type": headers.get("content-type"),
        "title": title,
        "robots_txt": robots,
        "sitemap_xml": sitemap,
        "method": method,
    }


def _trust_score(domain_data: Dict[str, Any]) -> Dict[str, Any]:
    score = 50
    signals: List[str] = []
    deductions: List[str] = []

    whois = domain_data.get("whois", {})
    tls = domain_data.get("tls", {})
    web = domain_data.get("web", {})
    dns = domain_data.get("records", {})
    subdomains = domain_data.get("subdomains", [])

    if whois.get("creation_date"):
        score += 8
        signals.append("WHOIS creation date present")
    else:
        deductions.append("WHOIS creation date unavailable")

    if tls.get("issuer"):
        score += 6
        signals.append("TLS certificate present")
    else:
        deductions.append("No TLS certificate metadata")

    if dns.get("TXT"):
        txt_joined = " ".join(_normalize_record_values(dns.get("TXT"))).lower()
        if "v=spf1" in txt_joined:
            score += 5
            signals.append("SPF record present")
        else:
            deductions.append("No SPF record detected")
        if "v=dmarc1" in txt_joined:
            score += 4
            signals.append("DMARC record present")
    else:
        deductions.append("No TXT policy records")

    if len(subdomains) >= 5:
        score += 6
        signals.append("Multiple active subdomains discovered")
    elif len(subdomains) == 0:
        deductions.append("No active subdomains discovered")

    if web.get("status_code") in {200, 301, 302}:
        score += 8
        signals.append("Website responds over HTTP(S)")
    else:
        deductions.append("Web endpoint not confirmed")

    if web.get("server"):
        score += 2
        signals.append("Server header exposed")

    if whois.get("expiration_date"):
        score += 3
        signals.append("Expiration date present")

    score = max(0, min(100, score))
    rating = "high" if score >= 75 else "medium" if score >= 45 else "low"

    return {
        "risk_score": score,
        "risk_rating": rating,
        "risk_signals": signals,
        "warnings": deductions,
        "note": "Heuristic trust score based on public signals, not a definitive fraud verdict.",
    }


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
        # If no scheme provided (e.g., just an IP like 16.16.25.208), default to socks5://
        if "://" not in proxy:
            proxy = f"socks5://{proxy}"
        kwargs["proxy"] = proxy
    return httpx.AsyncClient(**kwargs)


async def _hunt_s3_buckets(domain: str) -> Dict[str, Any]:
    """
    Scan for publicly exposed AWS S3 buckets associated with a target domain.
    
    Strategy:
    1. Extract base domain name (e.g., "example.com" -> "example")
    2. Generate 50+ common bucket name permutations
    3. Check each against https://[bucket].s3.amazonaws.com
    4. Mark as "Open/Vulnerable" (200), "Secure/Closed" (403), or "Not Found" (404)
    
    Returns:
        {
            "base_name": "example",
            "total_checked": 52,
            "found": {
                "example-dev": {"status": 200, "label": "Open/Vulnerable"},
                "example-backup": {"status": 403, "label": "Secure/Closed"},
                ...
            },
            "vulnerable_buckets": ["example-dev", ...],
            "secure_buckets": ["example-backup", ...],
            "vulnerable_count": 1,
            "secure_count": 3
        }
    """
    # Extract base domain name (e.g., "example.com" -> "example")
    domain_clean = domain.replace("https://", "").replace("http://", "").split("/")[0]
    base_name = domain_clean.split(".")[0].lower()
    
    # Generate 50+ common S3 bucket name permutations
    bucket_names = _generate_s3_bucket_names(base_name)
    
    found_buckets: Dict[str, Dict[str, Any]] = {}
    vulnerable = []
    secure = []
    
    # Check each bucket asynchronously
    async with _httpx_client(proxy=None, timeout=5) as client:
        tasks = [_check_s3_bucket(client, bucket) for bucket in bucket_names]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for bucket, result in zip(bucket_names, results):
            if isinstance(result, Exception):
                # Timeout or connection error
                continue
            
            status, label = result
            if status == 200:
                found_buckets[bucket] = {"status": status, "label": "Open/Vulnerable"}
                vulnerable.append(bucket)
            elif status == 403:
                found_buckets[bucket] = {"status": status, "label": "Secure/Closed"}
                secure.append(bucket)
            # Ignore 404s
    
    return {
        "base_name": base_name,
        "total_checked": len(bucket_names),
        "found": found_buckets,
        "vulnerable_buckets": vulnerable,
        "secure_buckets": secure,
        "vulnerable_count": len(vulnerable),
        "secure_count": len(secure),
        "note": "Open buckets (200) allow public read/write. Secure buckets (403) deny access. Check bucket policies and ACLs manually."
    }


async def _check_s3_bucket(client: httpx.AsyncClient, bucket_name: str) -> tuple[int, str]:
    """
    Check a single S3 bucket by sending a HEAD request.
    Returns: (status_code, label)
    """
    url = f"https://{bucket_name}.s3.amazonaws.com/"
    try:
        response = await client.head(url)
        return (response.status_code, "")
    except (httpx.TimeoutException, httpx.ConnectError, asyncio.TimeoutError):
        # Timeouts are treated as buckets that don't exist
        return None
    except Exception:
        return None


def _generate_s3_bucket_names(base_name: str) -> List[str]:
    """
    Generate 50+ common S3 bucket name permutations for a given base name.
    Covers common patterns: dev, prod, backup, staging, test, etc.
    """
    permutations = [
        # Direct naming
        base_name,
        f"{base_name}-bucket",
        
        # Environment variants
        f"{base_name}-dev",
        f"{base_name}-prod",
        f"{base_name}-staging",
        f"{base_name}-test",
        f"{base_name}-qa",
        f"{base_name}-stg",
        "dev-{base_name}",
        "prod-{base_name}",
        "staging-{base_name}",
        "test-{base_name}",
        
        # Backup & Archive
        f"{base_name}-backup",
        f"{base_name}-backups",
        f"{base_name}-archive",
        "backup-{base_name}",
        "backups-{base_name}",
        "archive-{base_name}",
        f"{base_name}-old",
        
        # Data variants
        f"{base_name}-data",
        f"{base_name}-logs",
        f"{base_name}-uploads",
        f"{base_name}-images",
        f"{base_name}-cdn",
        f"{base_name}-media",
        f"{base_name}-assets",
        f"{base_name}-static",
        "data-{base_name}",
        "logs-{base_name}",
        "uploads-{base_name}",
        
        # Private/Secret keywords (often left exposed)
        f"{base_name}-private",
        f"{base_name}-secret",
        f"{base_name}-internal",
        f"{base_name}-admin",
        f"{base_name}-config",
        f"{base_name}-credentials",
        f"{base_name}-keys",
        "private-{base_name}",
        "secret-{base_name}",
        
        # Build & Release
        f"{base_name}-build",
        f"{base_name}-release",
        f"{base_name}-deploy",
        "build-{base_name}",
        "release-{base_name}",
        
        # Variants with dashes/numbers
        f"{base_name}-1",
        f"{base_name}-2",
        f"{base_name}-us",
        f"{base_name}-eu",
        f"{base_name}-asia",
    ]
    
    # Format with base_name substitution and convert to lowercase
    result = []
    for name in permutations:
        formatted = name.format(base_name=base_name) if "{base_name}" in name else name
        result.append(formatted.lower())
    
    return list(dict.fromkeys(result))  # Remove duplicates while preserving order


async def _domain_lookup(domain: str) -> Dict[str, Any]:
    resolver = dns.asyncresolver.Resolver()
    record_types = ["A", "MX", "TXT", "NS", "AAAA", "CNAME"]
    records: Dict[str, Any] = {}

    # DNS Records — Handled individually to prevent total failure
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
            records[record_type] = f"lookup_error: {type(exc).__name__}"

    # Global sub-module isolation
    async def _safe_run(name: str, coro):
        try:
            return await coro
        except Exception as e:
            logger.error(f"Module '{name}' failed for {domain}: {e}")
            return {"error": f"{type(e).__name__}: {str(e)}", "module_failed": True}

    return {
        "domain": domain,
        "records": records,
        "source": "dns_asyncresolver",
        "whois": await _safe_run("whois", _whois_lookup(domain)),
        "subdomains": await _safe_run("subdomains", _common_subdomains(domain)),
        "tls": await _safe_run("tls", _tls_metadata(domain)),
        "web": await _safe_run("web", _web_fingerprint(domain)),
        "s3_buckets": await _safe_run("s3_buckets", _hunt_s3_buckets(domain)),
        "hardened_mode": True
    }


async def _ip_lookup(ip: str) -> Dict[str, Any]:
    """Gather deep intelligence on a target IP address."""
    result: Dict[str, Any] = {
        "ip": ip,
        "hostname": "resolving...",
        "asn": None,
        "company": None,
        "isp": None,
        "city": None,
        "region": None,
        "country": None,
        "loc": None,
        "timezone": None,
        "is_proxy": False,
        "is_vpn": False,
        "is_tor": False,
        "status": "partial"
    }

    # Reverse DNS
    try:
        loop = asyncio.get_event_loop()
        names = await loop.run_in_executor(None, socket.gethostbyaddr, ip)
        result["hostname"] = names[0] if names else "no reverse dns"
    except Exception:
        result["hostname"] = "lookup failed"

    # IPInfo / ASN Data
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(f"https://ipapi.co/{ip}/json/")
            if resp.status_code == 200:
                data = resp.json()
                result.update({
                    "asn": data.get("asn"),
                    "isp": data.get("org"),
                    "company": data.get("org"),
                    "city": data.get("city"),
                    "region": data.get("region"),
                    "country": data.get("country_name"),
                    "loc": f"{data.get('latitude')},{data.get('longitude')}",
                    "timezone": data.get("timezone"),
                    "status": "success"
                })
    except Exception as e:
         logger.error(f"IP lookup failed for {ip}: {e}")

    return result


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
    """Multi-platform username OSINT — GitHub, Reddit, HackerNews, and Twitter/X."""

    async def _check_github() -> Dict[str, Any]:
        url = f"https://github.com/{username}"
        try:
            async with _httpx_client(proxy=proxy, timeout=timeout) as client:
                response = await client.get(url)
            if response.status_code == 404:
                return {"platform": "GitHub", "username": username, "profile_found": False, "url": url}
            if response.status_code != 200:
                return {"platform": "GitHub", "username": username, "profile_found": False, "url": url, "error": f"HTTP {response.status_code}"}
            
            # Simple assumption: 200 OK means it was found. Try to extract name/bio gracefully.
            soup = BeautifulSoup(response.text, "lxml")
            name_tag = soup.find("span", {"itemprop": "name"}) or soup.find("h1", class_=re.compile(r"h2-mktg|h1"))
            bio_tag = soup.find("div", class_=re.compile(r"p-note|color-fg-muted", re.I))
            avatar_tag = soup.find("img", class_=re.compile(r"avatar", re.I))
            
            return {
                "platform": "GitHub",
                "username": username,
                "profile_found": True,
                "url": url,
                "display_name": name_tag.get_text(strip=True) if name_tag else None,
                "bio": bio_tag.get_text(strip=True) if bio_tag else None,
                "avatar_url": avatar_tag.get("src") if avatar_tag else None,
            }
        except Exception as exc:
            return {"platform": "GitHub", "username": username, "profile_found": False, "url": url, "error": str(exc)}

    async def _check_reddit() -> Dict[str, Any]:
        url = f"https://www.reddit.com/user/{username}/about.json"
        profile_url = f"https://www.reddit.com/u/{username}"
        try:
            async with _httpx_client(proxy=proxy, timeout=timeout) as client:
                resp = await client.get(url)
            if resp.status_code == 404:
                return {"platform": "Reddit", "username": username, "profile_found": False, "url": profile_url}
            if resp.status_code != 200:
                return {"platform": "Reddit", "username": username, "profile_found": False, "url": profile_url, "error": f"HTTP {resp.status_code}"}
            data = resp.json().get("data", {})
            return {
                "platform": "Reddit",
                "username": username,
                "profile_found": True,
                "url": profile_url,
                "display_name": data.get("name"),
                "karma": data.get("total_karma"),
                "link_karma": data.get("link_karma"),
                "comment_karma": data.get("comment_karma"),
                "account_age_days": int((time.time() - data["created_utc"]) / 86400) if data.get("created_utc") else None,
                "is_gold": data.get("is_gold", False),
                "avatar_url": data.get("icon_img"),
            }
        except Exception as exc:
            return {"platform": "Reddit", "username": username, "profile_found": False, "url": profile_url, "error": str(exc)}

    async def _check_hackernews() -> Dict[str, Any]:
        url = f"https://hacker-news.firebaseio.com/v0/user/{username}.json"
        profile_url = f"https://news.ycombinator.com/user?id={username}"
        try:
            async with _httpx_client(proxy=proxy, timeout=timeout) as client:
                resp = await client.get(url)
            data = resp.json()
            if not data:
                return {"platform": "HackerNews", "username": username, "profile_found": False, "url": profile_url}
            soup = BeautifulSoup(data.get("about", "") or "", "lxml")
            about_text = soup.get_text(strip=True)
            return {
                "platform": "HackerNews",
                "username": username,
                "profile_found": True,
                "url": profile_url,
                "karma": data.get("karma"),
                "account_age_days": int((time.time() - data["created"]) / 86400) if data.get("created") else None,
                "submission_count": len(data.get("submitted", [])),
                "bio": about_text or None,
            }
        except Exception as exc:
            return {"platform": "HackerNews", "username": username, "profile_found": False, "url": profile_url, "error": str(exc)}

    async def _check_twitter() -> Dict[str, Any]:
        url = f"https://twitter.com/{username}"
        profile_url = f"https://x.com/{username}"
        try:
            async with _httpx_client(proxy=proxy, timeout=timeout) as client:
                resp = await client.get(url)
            if resp.status_code == 404:
                return {"platform": "Twitter/X", "username": username, "profile_found": False, "url": profile_url}
            # Twitter blocks server-side scraping — we can only detect existence
            profile_found = resp.status_code == 200 and "twitter.com" in resp.url.host
            return {
                "platform": "Twitter/X",
                "username": username,
                "profile_found": profile_found,
                "url": profile_url,
                "note": "Twitter blocks server-side scraping; only existence confirmed.",
            }
        except Exception as exc:
            return {"platform": "Twitter/X", "username": username, "profile_found": False, "url": profile_url, "error": str(exc)}

    # Run all platform checks concurrently
    results = await asyncio.gather(
        _check_github(),
        _check_reddit(),
        _check_hackernews(),
        _check_twitter(),
        return_exceptions=False,
    )

    platforms = list(results)
    found_count = sum(1 for p in platforms if p.get("profile_found"))

    return {
        "username": username,
        "platforms_checked": len(platforms),
        "profiles_found": found_count,
        "platforms": platforms,
    }


# ═══════════════════════════════════════════════════════════════════
# THEATER 1 — DARK WEB / ONION CRAWLER
# Maps to: TorBot, Fresh Onions, OnionScan, Onioff, Tor Crawl
# ═══════════════════════════════════════════════════════════════════

async def _check_tor_health() -> Dict[str, Any]:
    """Verify that the local Tor SOCKS5 proxy is live and working."""
    start_time = time.time()
    try:
        async with httpx.AsyncClient(
            proxy=TOR_PROXY_URL,
            timeout=10,
            headers={"User-Agent": _pick_user_agent()},
            follow_redirects=True,
        ) as client:
            resp = await client.get("https://check.torproject.org/api/ip")
            data = resp.json()
            latency = round((time.time() - start_time) * 1000, 2)
            return {
                "tor_running": data.get("IsTor", False),
                "exit_ip": data.get("IP"),
                "proxy_url": TOR_PROXY_URL,
                "latency_ms": latency,
                "status": "connected"
            }
    except httpx.ConnectTimeout:
        return {
            "tor_running": False,
            "status": "timeout",
            "proxy_url": TOR_PROXY_URL,
            "error": "Connection timed out. Check AWS Security Group (Inbound Port 9050)."
        }
    except httpx.ConnectError:
        return {
            "tor_running": False,
            "status": "refused",
            "proxy_url": TOR_PROXY_URL,
            "error": "Connection refused. Check if Tor service is running on EC2."
        }
    except Exception as exc:
        return {
            "tor_running": False,
            "status": "error",
            "proxy_url": TOR_PROXY_URL,
            "error": f"{type(exc).__name__}: {str(exc)}"
        }


async def _onion_crawler(onion_url: str) -> Dict[str, Any]:
    """
    Crawl a .onion hidden service via the local Tor SOCKS5 proxy.
    Extracts: page title, text excerpt, discovered .onion URLs on the page,
    and any email addresses visible in the HTML.
    """
    # Normalise URL
    if not onion_url.startswith("http"):
        onion_url = f"http://{onion_url}"

    # Verify Tor is running before attempting the crawl
    tor_status = await _check_tor_health()
    if not tor_status["tor_running"]:
        return {
            "url": onion_url,
            "crawl_success": False,
            "tor_status": tor_status,
            "error": (
                "Tor proxy is not running or is unreachable at "
                f"{TOR_PROXY_URL}. Please start the Tor service and retry."
            ),
        }

    try:
        async with httpx.AsyncClient(
            proxy=TOR_PROXY_URL,
            timeout=TOR_TIMEOUT,
            headers={
                "User-Agent": _pick_user_agent(),
                "Accept-Language": "en-US,en;q=0.9",
            },
            follow_redirects=True,
            verify=False,  # .onion sites rarely have valid certs
        ) as client:
            response = await client.get(onion_url)
            http_status = response.status_code
            html = response.text
    except httpx.TimeoutException:
        return {
            "url": onion_url,
            "crawl_success": False,
            "tor_status": tor_status,
            "error": f"Request timed out after {TOR_TIMEOUT}s. The hidden service may be offline.",
        }
    except Exception as exc:
        return {
            "url": onion_url,
            "crawl_success": False,
            "tor_status": tor_status,
            "error": str(exc),
        }

    soup = BeautifulSoup(html, "lxml")

    # Extract page title
    title = soup.title.get_text(strip=True) if soup.title else None

    # Extract visible text excerpt (first 1000 chars)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text_excerpt = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()[:1500]

    # Discover all .onion links on the page
    onion_links: List[str] = []
    seen_onions: set = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        onion_match = re.search(r"https?://[a-z2-7]{16,56}\.onion[^\s'\"]*", href, re.I)
        bare_match = re.search(r"[a-z2-7]{16,56}\.onion", href, re.I)
        if onion_match:
            found = onion_match.group(0)
        elif bare_match:
            found = f"http://{bare_match.group(0)}"
        else:
            continue
        if found not in seen_onions:
            seen_onions.add(found)
            onion_links.append(found)

    # Extract email addresses from visible text
    emails_found = list(set(re.findall(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        html
    )))[:20]

    # Extract meta tags
    meta_tags: Dict[str, str] = {}
    for meta in soup.find_all("meta"):
        name = meta.get("name") or meta.get("property") or ""
        content = meta.get("content", "")
        if name and content:
            meta_tags[name.lower()] = content[:300]

    return {
        "url": onion_url,
        "crawl_success": True,
        "http_status": http_status,
        "tor_status": tor_status,
        "title": title,
        "text_excerpt": text_excerpt,
        "onion_links_discovered": onion_links[:50],
        "onion_links_count": len(onion_links),
        "emails_found": emails_found,
        "meta_tags": meta_tags,
        "note": "Single-depth crawl. Links discovered are NOT automatically followed.",
    }


# ═══════════════════════════════════════════════════════════════════
# THEATER 2 — GENERAL RECON & FOOTPRINTING: PHONE
# Maps to: Skip Tracer, GASMask, Final Recon, PhoneInfoga
# ═══════════════════════════════════════════════════════════════════

# ── Indian telecom carrier/circle tables ─────────────────────────
_INDIA_CARRIER_SERIES: Dict[str, Dict[str, str]] = {
    # Jio series (4xxx, some 7xxx, 8xxx, 9xxx)
    "6000": {"carrier": "Jio", "circle": "Delhi"},
    "6001": {"carrier": "Jio", "circle": "Delhi"},
    "6002": {"carrier": "Jio", "circle": "Mumbai"},
    "6003": {"carrier": "Jio", "circle": "Maharashtra"},
    "6004": {"carrier": "Jio", "circle": "Karnataka"},
    "6005": {"carrier": "Jio", "circle": "Tamil Nadu"},
    "6006": {"carrier": "Jio", "circle": "Andhra Pradesh"},
    "6007": {"carrier": "Jio", "circle": "Gujarat"},
    "6008": {"carrier": "Jio", "circle": "Rajasthan"},
    "6009": {"carrier": "Jio", "circle": "Uttar Pradesh"},
    "7000": {"carrier": "Jio", "circle": "West Bengal"},
    "7001": {"carrier": "Jio", "circle": "Kerala"},
    "7002": {"carrier": "Jio", "circle": "Odisha"},
    "7003": {"carrier": "Jio", "circle": "Punjab"},
    "7004": {"carrier": "Jio", "circle": "Bihar"},
    "7005": {"carrier": "Jio", "circle": "Jharkhand"},
    "7006": {"carrier": "Jio", "circle": "Assam"},
    "7007": {"carrier": "Jio", "circle": "Jammu & Kashmir"},
    "7008": {"carrier": "Jio", "circle": "Himachal Pradesh"},
    "7009": {"carrier": "Jio", "circle": "North East"},
    # Airtel series
    "9800": {"carrier": "Airtel", "circle": "West Bengal"},
    "9801": {"carrier": "Airtel", "circle": "Andhra Pradesh"},
    "9802": {"carrier": "Airtel", "circle": "Uttarakhand"},
    "9803": {"carrier": "Airtel", "circle": "Himachal Pradesh"},
    "9870": {"carrier": "Airtel", "circle": "Delhi"},
    "9871": {"carrier": "Airtel", "circle": "Delhi"},
    "9818": {"carrier": "Airtel", "circle": "Delhi"},
    "9910": {"carrier": "Airtel", "circle": "Delhi"},
    "9999": {"carrier": "Airtel", "circle": "Delhi"},
    "9953": {"carrier": "Airtel", "circle": "Delhi"},
    "9958": {"carrier": "Airtel", "circle": "Delhi"},
    "9891": {"carrier": "Airtel", "circle": "Delhi"},
    "9821": {"carrier": "Airtel", "circle": "Mumbai"},
    "9819": {"carrier": "Airtel", "circle": "Mumbai"},
    "9320": {"carrier": "Airtel", "circle": "Mumbai"},
    "9324": {"carrier": "Airtel", "circle": "Mumbai"},
    "9773": {"carrier": "Airtel", "circle": "Maharashtra"},
    "9881": {"carrier": "Airtel", "circle": "Maharashtra"},
    "9886": {"carrier": "Airtel", "circle": "Karnataka"},
    "9900": {"carrier": "Airtel", "circle": "Karnataka"},
    "9842": {"carrier": "Airtel", "circle": "Tamil Nadu"},
    "9944": {"carrier": "Airtel", "circle": "Tamil Nadu"},
    "9414": {"carrier": "Airtel", "circle": "Rajasthan"},
    "9887": {"carrier": "Airtel", "circle": "Rajasthan"},
    "9824": {"carrier": "Airtel", "circle": "Gujarat"},
    "9825": {"carrier": "Airtel", "circle": "Gujarat"},
    # Vodafone/Vi series
    "9820": {"carrier": "Vi (Vodafone Idea)", "circle": "Mumbai"},
    "9930": {"carrier": "Vi (Vodafone Idea)", "circle": "Mumbai"},
    "9867": {"carrier": "Vi (Vodafone Idea)", "circle": "Mumbai"},
    "9819": {"carrier": "Vi (Vodafone Idea)", "circle": "Mumbai"},
    "9833": {"carrier": "Vi (Vodafone Idea)", "circle": "Mumbai"},
    "9811": {"carrier": "Vi (Vodafone Idea)", "circle": "Delhi"},
    "9312": {"carrier": "Vi (Vodafone Idea)", "circle": "Delhi"},
    "9717": {"carrier": "Vi (Vodafone Idea)", "circle": "Delhi"},
    "9990": {"carrier": "Vi (Vodafone Idea)", "circle": "Delhi"},
    "9886": {"carrier": "Vi (Vodafone Idea)", "circle": "Karnataka"},
    "9916": {"carrier": "Vi (Vodafone Idea)", "circle": "Karnataka"},
    # BSNL series
    "9415": {"carrier": "BSNL", "circle": "Uttar Pradesh"},
    "9451": {"carrier": "BSNL", "circle": "Uttar Pradesh"},
    "9452": {"carrier": "BSNL", "circle": "Uttar Pradesh"},
    "9453": {"carrier": "BSNL", "circle": "Uttar Pradesh"},
    "9454": {"carrier": "BSNL", "circle": "Uttar Pradesh"},
    "9455": {"carrier": "BSNL", "circle": "Uttar Pradesh"},
    "9456": {"carrier": "BSNL", "circle": "Uttar Pradesh"},
    "9457": {"carrier": "BSNL", "circle": "Uttar Pradesh"},
    "9458": {"carrier": "BSNL", "circle": "Uttar Pradesh"},
    "9459": {"carrier": "BSNL", "circle": "Uttar Pradesh"},
    "9436": {"carrier": "BSNL", "circle": "North East"},
    "9437": {"carrier": "BSNL", "circle": "Odisha"},
    "9431": {"carrier": "BSNL", "circle": "Bihar"},
    "9433": {"carrier": "BSNL", "circle": "West Bengal"},
    "9434": {"carrier": "BSNL", "circle": "Assam"},
}

_INDIA_PREFIX_CARRIER: Dict[str, Dict[str, str]] = {
    # Jio (reliance)
    "700": {"carrier": "Jio", "line_type": "mobile"},
    "701": {"carrier": "Jio", "line_type": "mobile"},
    "702": {"carrier": "Jio", "line_type": "mobile"},
    "703": {"carrier": "Jio", "line_type": "mobile"},
    "704": {"carrier": "Jio", "line_type": "mobile"},
    "705": {"carrier": "Jio", "line_type": "mobile"},
    "706": {"carrier": "Jio", "line_type": "mobile"},
    "707": {"carrier": "Jio", "line_type": "mobile"},
    "708": {"carrier": "Jio", "line_type": "mobile"},
    "709": {"carrier": "Jio", "line_type": "mobile"},
    "600": {"carrier": "Jio", "line_type": "mobile"},
    "601": {"carrier": "Jio", "line_type": "mobile"},
    "602": {"carrier": "Jio", "line_type": "mobile"},
    "603": {"carrier": "Jio", "line_type": "mobile"},
    "604": {"carrier": "Jio", "line_type": "mobile"},
    "605": {"carrier": "Jio", "line_type": "mobile"},
    "606": {"carrier": "Jio", "line_type": "mobile"},
    "607": {"carrier": "Jio", "line_type": "mobile"},
    "608": {"carrier": "Jio", "line_type": "mobile"},
    "609": {"carrier": "Jio", "line_type": "mobile"},
    "800": {"carrier": "Jio", "line_type": "mobile"},
    "801": {"carrier": "Jio", "line_type": "mobile"},
    "802": {"carrier": "Jio", "line_type": "mobile"},
    "803": {"carrier": "Jio", "line_type": "mobile"},
    "804": {"carrier": "Jio", "line_type": "mobile"},
    "805": {"carrier": "Jio", "line_type": "mobile"},
    "806": {"carrier": "Jio", "line_type": "mobile"},
    "807": {"carrier": "Jio", "line_type": "mobile"},
    "808": {"carrier": "Jio", "line_type": "mobile"},
    "809": {"carrier": "Jio", "line_type": "mobile"},
    # Airtel
    "620": {"carrier": "Airtel", "line_type": "mobile"},
    "621": {"carrier": "Airtel", "line_type": "mobile"},
    "622": {"carrier": "Airtel", "line_type": "mobile"},
    "623": {"carrier": "Airtel", "line_type": "mobile"},
    "624": {"carrier": "Airtel", "line_type": "mobile"},
    "625": {"carrier": "Airtel", "line_type": "mobile"},
    "626": {"carrier": "Airtel", "line_type": "mobile"},
    "627": {"carrier": "Airtel", "line_type": "mobile"},
    "628": {"carrier": "Airtel", "line_type": "mobile"},
    "629": {"carrier": "Airtel", "line_type": "mobile"},
    "720": {"carrier": "Airtel", "line_type": "mobile"},
    "721": {"carrier": "Airtel", "line_type": "mobile"},
    "730": {"carrier": "Airtel", "line_type": "mobile"},
    "731": {"carrier": "Airtel", "line_type": "mobile"},
    "740": {"carrier": "Airtel", "line_type": "mobile"},
    "741": {"carrier": "Airtel", "line_type": "mobile"},
    "742": {"carrier": "Airtel", "line_type": "mobile"},
    "820": {"carrier": "Airtel", "line_type": "mobile"},
    "821": {"carrier": "Airtel", "line_type": "mobile"},
    "900": {"carrier": "Airtel", "line_type": "mobile"},
    "901": {"carrier": "Airtel", "line_type": "mobile"},
    "902": {"carrier": "Airtel", "line_type": "mobile"},
    "903": {"carrier": "Airtel", "line_type": "mobile"},
    "904": {"carrier": "Airtel", "line_type": "mobile"},
    "905": {"carrier": "Airtel", "line_type": "mobile"},
    "906": {"carrier": "Airtel", "line_type": "mobile"},
    "907": {"carrier": "Airtel", "line_type": "mobile"},
    "908": {"carrier": "Airtel", "line_type": "mobile"},
    "909": {"carrier": "Airtel", "line_type": "mobile"},
    "910": {"carrier": "Airtel", "line_type": "mobile"},
    "911": {"carrier": "Airtel", "line_type": "mobile"},
    "912": {"carrier": "Airtel", "line_type": "mobile"},
    "913": {"carrier": "Airtel", "line_type": "mobile"},
    "914": {"carrier": "Airtel", "line_type": "mobile"},
    "915": {"carrier": "Airtel", "line_type": "mobile"},
    "916": {"carrier": "Airtel", "line_type": "mobile"},
    "917": {"carrier": "Airtel", "line_type": "mobile"},
    "918": {"carrier": "Airtel", "line_type": "mobile"},
    "919": {"carrier": "Airtel", "line_type": "mobile"},
    "995": {"carrier": "Airtel", "line_type": "mobile"},
    "996": {"carrier": "Airtel", "line_type": "mobile"},
    "997": {"carrier": "Airtel", "line_type": "mobile"},
    "998": {"carrier": "Airtel", "line_type": "mobile"},
    "999": {"carrier": "Airtel", "line_type": "mobile"},
    # Vi (Vodafone Idea)
    "630": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "631": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "632": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "633": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "634": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "635": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "636": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "637": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "638": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "639": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "750": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "751": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "752": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "753": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "754": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "755": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "756": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "930": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "931": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "932": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "933": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "934": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "935": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "936": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "937": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "938": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "939": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "980": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "981": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "982": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "983": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "984": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "985": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "986": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "987": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "988": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    "989": {"carrier": "Vi (Vodafone Idea)", "line_type": "mobile"},
    # BSNL
    "940": {"carrier": "BSNL", "line_type": "mobile"},
    "941": {"carrier": "BSNL", "line_type": "mobile"},
    "942": {"carrier": "BSNL", "line_type": "mobile"},
    "943": {"carrier": "BSNL", "line_type": "mobile"},
    "944": {"carrier": "BSNL", "line_type": "mobile"},
    "945": {"carrier": "BSNL", "line_type": "mobile"},
    "946": {"carrier": "BSNL", "line_type": "mobile"},
    "947": {"carrier": "BSNL", "line_type": "mobile"},
    "948": {"carrier": "BSNL", "line_type": "mobile"},
    "949": {"carrier": "BSNL", "line_type": "mobile"},
    # MTNL
    "222": {"carrier": "MTNL", "line_type": "landline"},
    "223": {"carrier": "MTNL", "line_type": "landline"},
    "224": {"carrier": "MTNL", "line_type": "landline"},
}


def _detect_india_carrier(local_digits: str) -> Dict[str, str]:
    """Detect Indian carrier and circle from the 10-digit local number."""
    if len(local_digits) < 4:
        return {}
    series4 = local_digits[:4]
    series3 = local_digits[:3]
    if series4 in _INDIA_CARRIER_SERIES:
        info = _INDIA_CARRIER_SERIES[series4]
        return {"carrier": info["carrier"], "circle": info.get("circle"), "line_type": "mobile"}
    if series3 in _INDIA_PREFIX_CARRIER:
        info = _INDIA_PREFIX_CARRIER[series3]
        return {"carrier": info["carrier"], "line_type": info.get("line_type", "mobile")}
    return {}


async def _phone_lookup(phone: str) -> Dict[str, Any]:
    """
    Comprehensive phone number OSINT:
    - NumVerify API (paid, most accurate) when key is set
    - Abstract API free phone validation
    - Indian telecom carrier/circle detection (offline, always available for +91)
    - Social media profile discovery via phone (WhatsApp link, Telegram, GitHub)
    - Possible username patterns extracted from number
    """
    # Normalize: strip all non-digit characters except leading +
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    if not cleaned.startswith("+"):
        cleaned = f"+{cleaned}"

    result: Dict[str, Any] = {
        "input": phone,
        "normalized": cleaned,
        "carrier": None,
        "line_type": None,
        "location": None,
        "country_code": None,
        "country_name": None,
        "valid": None,
        "is_mobile": None,
        "source": None,
        "social_links": [],
        "india_telecom": None,
        "possible_usernames": [],
    }

    # ── NumVerify API (paid, accurate) ───────────────────────────
    if NUMVERIFY_API_KEY:
        try:
            url = "http://apilayer.net/api/validate"
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(url, params={
                    "access_key": NUMVERIFY_API_KEY,
                    "number": cleaned,
                    "country_code": "",
                    "format": "1",
                })
                data = resp.json()
            if data.get("valid") is not False:
                result.update({
                    "valid": data.get("valid"),
                    "carrier": data.get("carrier"),
                    "line_type": data.get("line_type"),
                    "location": data.get("location"),
                    "country_code": data.get("country_code"),
                    "country_name": data.get("country_name"),
                    "is_mobile": data.get("line_type") == "mobile" if data.get("line_type") else None,
                    "local_format": data.get("local_format"),
                    "international_format": data.get("international_format"),
                    "source": "NumVerify API",
                })
        except Exception as exc:
            result["numverify_error"] = str(exc)

    # ── Country prefix table (always runs, enriches missing fields) ──
    country_prefixes = {
        "+1": ("US/CA", "United States / Canada"),
        "+44": ("GB", "United Kingdom"),
        "+91": ("IN", "India"),
        "+49": ("DE", "Germany"),
        "+33": ("FR", "France"),
        "+81": ("JP", "Japan"),
        "+86": ("CN", "China"),
        "+7": ("RU", "Russia"),
        "+55": ("BR", "Brazil"),
        "+61": ("AU", "Australia"),
        "+39": ("IT", "Italy"),
        "+34": ("ES", "Spain"),
        "+82": ("KR", "South Korea"),
        "+31": ("NL", "Netherlands"),
        "+971": ("AE", "United Arab Emirates"),
        "+966": ("SA", "Saudi Arabia"),
        "+20": ("EG", "Egypt"),
        "+27": ("ZA", "South Africa"),
        "+52": ("MX", "Mexico"),
        "+65": ("SG", "Singapore"),
        "+60": ("MY", "Malaysia"),
        "+63": ("PH", "Philippines"),
        "+62": ("ID", "Indonesia"),
        "+92": ("PK", "Pakistan"),
        "+880": ("BD", "Bangladesh"),
        "+94": ("LK", "Sri Lanka"),
        "+977": ("NP", "Nepal"),
        "+98": ("IR", "Iran"),
        "+90": ("TR", "Turkey"),
        "+234": ("NG", "Nigeria"),
        "+254": ("KE", "Kenya"),
        "+255": ("TZ", "Tanzania"),
        "+256": ("UG", "Uganda"),
        "+263": ("ZW", "Zimbabwe"),
        "+212": ("MA", "Morocco"),
        "+216": ("TN", "Tunisia"),
        "+213": ("DZ", "Algeria"),
        "+64": ("NZ", "New Zealand"),
        "+48": ("PL", "Poland"),
        "+46": ("SE", "Sweden"),
        "+47": ("NO", "Norway"),
        "+45": ("DK", "Denmark"),
        "+358": ("FI", "Finland"),
        "+41": ("CH", "Switzerland"),
        "+43": ("AT", "Austria"),
        "+32": ("BE", "Belgium"),
        "+351": ("PT", "Portugal"),
        "+30": ("GR", "Greece"),
        "+380": ("UA", "Ukraine"),
        "+420": ("CZ", "Czech Republic"),
        "+36": ("HU", "Hungary"),
        "+40": ("RO", "Romania"),
        "+359": ("BG", "Bulgaria"),
        "+385": ("HR", "Croatia"),
        "+381": ("RS", "Serbia"),
        "+66": ("TH", "Thailand"),
        "+84": ("VN", "Vietnam"),
        "+95": ("MM", "Myanmar"),
        "+856": ("LA", "Laos"),
        "+855": ("KH", "Cambodia"),
        "+886": ("TW", "Taiwan"),
        "+852": ("HK", "Hong Kong"),
        "+853": ("MO", "Macau"),
        "+1242": ("BS", "Bahamas"),
        "+1264": ("AI", "Anguilla"),
        "+1268": ("AG", "Antigua and Barbuda"),
        "+1284": ("VG", "British Virgin Islands"),
        "+1345": ("KY", "Cayman Islands"),
        "+1649": ("TC", "Turks and Caicos Islands"),
        "+1758": ("LC", "Saint Lucia"),
        "+1868": ("TT", "Trinidad and Tobago"),
        "+54": ("AR", "Argentina"),
        "+56": ("CL", "Chile"),
        "+57": ("CO", "Colombia"),
        "+51": ("PE", "Peru"),
        "+58": ("VE", "Venezuela"),
        "+593": ("EC", "Ecuador"),
        "+591": ("BO", "Bolivia"),
        "+595": ("PY", "Paraguay"),
        "+598": ("UY", "Uruguay"),
    }
    detected_cc = result.get("country_code")
    detected_cn = result.get("country_name")
    if not detected_cc:
        for prefix, cc_info in sorted(country_prefixes.items(), key=lambda x: -len(x[0])):
            if cleaned.startswith(prefix):
                detected_cc, detected_cn = cc_info
                result.update({
                    "country_code": detected_cc,
                    "country_name": detected_cn,
                })
                if not result.get("source"):
                    result["source"] = "offline prefix table"
                break

    # ── India-specific deep carrier detection ────────────────────
    if cleaned.startswith("+91") and len(cleaned) == 13:
        local = cleaned[3:]  # 10-digit local number
        india_info = _detect_india_carrier(local)
        if india_info:
            result["india_telecom"] = {
                "local_number": local,
                "carrier": india_info.get("carrier"),
                "circle": india_info.get("circle"),
                "line_type": india_info.get("line_type", "mobile"),
                "is_mobile": india_info.get("line_type", "mobile") == "mobile",
                "whatsapp_link": f"https://wa.me/91{local}",
                "note": "Carrier detected from TRAI series allocation table",
            }
            if not result.get("carrier"):
                result["carrier"] = india_info.get("carrier")
            if not result.get("line_type"):
                result["line_type"] = india_info.get("line_type", "mobile")
            if not result.get("location"):
                result["location"] = india_info.get("circle")
            result["is_mobile"] = india_info.get("line_type", "mobile") == "mobile"
        else:
            result["india_telecom"] = {
                "local_number": local,
                "whatsapp_link": f"https://wa.me/91{local}",
                "note": "Number series not in local TRAI table; use NumVerify for accurate carrier.",
            }

    # ── Abstract API free phone validation (no key needed) ───────
    ABSTRACT_API_KEY = os.getenv("ABSTRACT_API_KEY", "")
    if ABSTRACT_API_KEY and not result.get("carrier"):
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(
                    "https://phonevalidation.abstractapi.com/v1/",
                    params={"api_key": ABSTRACT_API_KEY, "phone": cleaned.lstrip("+")},
                )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("valid"):
                    result.update({
                        "valid": data.get("valid"),
                        "carrier": data.get("carrier", {}).get("name"),
                        "line_type": data.get("type"),
                        "country_name": data.get("country", {}).get("name"),
                        "location": data.get("location"),
                        "is_mobile": data.get("type") in ("mobile", "mobile_or_landline"),
                        "source": "Abstract API",
                    })
        except Exception:
            pass

    # ── Social media discovery links ─────────────────────────────
    digits_only = cleaned.lstrip("+")
    social_links = []

    # WhatsApp check (universal)
    social_links.append({
        "platform": "WhatsApp",
        "url": f"https://wa.me/{digits_only}",
        "note": "Open chat to verify presence",
    })

    # Telegram (by phone) — only accessible via Telegram clients
    social_links.append({
        "platform": "Telegram",
        "url": f"https://t.me/+{digits_only}",
        "note": "Telegram resolves phone-to-username via client API",
    })

    # For Indian numbers, add Truecaller web search
    if cleaned.startswith("+91"):
        local = cleaned[3:]
        social_links.append({
            "platform": "Truecaller (web)",
            "url": f"https://www.truecaller.com/search/in/{local}",
            "note": "Requires Truecaller account to view full name",
        })
        social_links.append({
            "platform": "India TRAI DND Registry",
            "url": f"https://www.nccptrai.gov.in/nccpregistry/search.misc",
            "note": "Check if number is on Do-Not-Disturb list",
        })

    result["social_links"] = social_links

    # ── Possible username patterns ───────────────────────────────
    # Generate common username patterns from last 4/6 digits (often used by users)
    last4 = digits_only[-4:] if len(digits_only) >= 4 else digits_only
    last6 = digits_only[-6:] if len(digits_only) >= 6 else digits_only
    result["possible_usernames"] = [
        f"user{last4}",
        f"user{last6}",
        last4,
        last6,
    ]

    result["valid"] = bool(re.match(r"^\+[1-9]\d{6,14}$", cleaned))
    return result


# ═══════════════════════════════════════════════════════════════════
# THEATER 3 — IDENTITY & CREDENTIAL HUNTING
# Maps to: h8mail, OSINT-SPY, Sherlock, Social Mapper
# ═══════════════════════════════════════════════════════════════════

async def _email_lookup(email: str) -> Dict[str, Any]:
    """
    Comprehensive email identity OSINT:
    - Gravatar profile (display name, avatar, linked social accounts)
    - GitHub user search by email (public API)
    - Username extraction and multi-platform recon
    - HaveIBeenPwned breach and paste lookup (requires HIBP_API_KEY)
    - MX record validation
    - Social media discovery links
    """
    email = email.strip().lower()
    local_part = email.split("@")[0] if "@" in email else email
    domain = email.split("@")[-1] if "@" in email else ""

    result: Dict[str, Any] = {
        "email": email,
        "domain": domain,
        "local_part": local_part,
        "gravatar": None,
        "github_users": [],
        "username_recon": None,
        "breaches": None,
        "pastes": None,
        "mx_records": None,
        "breach_count": 0,
        "paste_count": 0,
        "social_links": [],
        "extracted_usernames": [],
    }

    # ── Username patterns extracted from email local part ────────
    # e.g. john.doe@gmail.com → ["johndoe", "john.doe", "john_doe", "john", "doe"]
    raw = local_part
    parts = re.split(r"[._\-+]", raw)
    candidates: List[str] = list(dict.fromkeys(filter(None, [
        raw,
        re.sub(r"[._\-+]", "", raw),
        re.sub(r"[._\-+]", "_", raw),
        re.sub(r"[._\-+]", ".", raw),
        parts[0] if parts else None,
        "".join(parts) if len(parts) > 1 else None,
    ])))
    result["extracted_usernames"] = candidates

    # ── Social media discovery links from email ──────────────────
    email_hash = hashlib.md5(email.encode("utf-8")).hexdigest()  # noqa: S324
    social_links = [
        {"platform": "Gravatar", "url": f"https://www.gravatar.com/{email_hash}", "note": "Profile if registered"},
        {"platform": "Google", "url": f"https://accounts.google.com/SignIn?Email={email}", "note": "Gmail account hint"},
    ]
    # Add username-based social links for the primary extracted username
    if candidates:
        primary = candidates[0]
        social_links += [
            {"platform": "GitHub", "url": f"https://github.com/{primary}", "note": "Check GitHub profile"},
            {"platform": "Twitter/X", "url": f"https://x.com/{primary}", "note": "Check Twitter/X profile"},
            {"platform": "Instagram", "url": f"https://www.instagram.com/{primary}/", "note": "Check Instagram profile"},
            {"platform": "LinkedIn", "url": f"https://www.linkedin.com/search/results/all/?keywords={primary}", "note": "LinkedIn search"},
            {"platform": "Reddit", "url": f"https://www.reddit.com/user/{primary}", "note": "Check Reddit profile"},
            {"platform": "Facebook", "url": f"https://www.facebook.com/search/top/?q={email}", "note": "Facebook search by email"},
            {"platform": "Telegram", "url": f"https://t.me/{primary}", "note": "Telegram username check"},
            {"platform": "Pinterest", "url": f"https://www.pinterest.com/{primary}/", "note": "Pinterest profile"},
            {"platform": "YouTube", "url": f"https://www.youtube.com/@{primary}", "note": "YouTube channel check"},
            {"platform": "TikTok", "url": f"https://www.tiktok.com/@{primary}", "note": "TikTok profile check"},
            {"platform": "Medium", "url": f"https://medium.com/@{primary}", "note": "Medium profile check"},
            {"platform": "Dev.to", "url": f"https://dev.to/{primary}", "note": "Dev.to profile check"},
            {"platform": "Quora", "url": f"https://www.quora.com/profile/{primary}", "note": "Quora profile check"},
        ]
    result["social_links"] = social_links

    # ── GitHub user search by email ──────────────────────────────
    try:
        github_headers = {
            "User-Agent": "NexusScope-OSINT/2.0",
            "Accept": "application/vnd.github.v3+json",
        }
        GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
        if GITHUB_TOKEN:
            github_headers["Authorization"] = f"token {GITHUB_TOKEN}"
        async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers=github_headers) as client:
            gh_resp = await client.get(
                "https://api.github.com/search/users",
                params={"q": f"{email} in:email", "per_page": 5},
            )
        if gh_resp.status_code == 200:
            gh_data = gh_resp.json()
            result["github_users"] = [
                {
                    "username": u.get("login"),
                    "profile_url": u.get("html_url"),
                    "avatar_url": u.get("avatar_url"),
                    "type": u.get("type"),
                }
                for u in gh_data.get("items", [])
            ]
    except Exception as exc:
        result["github_search_error"] = str(exc)

    # ── Username recon: run multi-platform lookup on primary username ─
    if candidates:
        try:
            result["username_recon"] = await _username_lookup(candidates[0], proxy=None, timeout=12)
        except Exception as exc:
            result["username_recon_error"] = str(exc)

    # ── Gravatar profile ─────────────────────────────────────────
    try:
        gravatar_url = f"https://www.gravatar.com/{email_hash}.json"
        async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers={"User-Agent": _pick_user_agent()}) as client:
            resp = await client.get(gravatar_url)
        if resp.status_code == 200:
            profile_data = resp.json().get("entry", [{}])[0]
            result["gravatar"] = {
                "found": True,
                "profile_url": f"https://www.gravatar.com/{email_hash}",
                "avatar_url": f"https://www.gravatar.com/avatar/{email_hash}?s=200",
                "display_name": profile_data.get("displayName"),
                "real_name": profile_data.get("name", {}).get("formatted"),
                "about_me": profile_data.get("aboutMe"),
                "location": profile_data.get("currentLocation"),
                "accounts": [
                    {"shortname": acc.get("shortname"), "url": acc.get("url")}
                    for acc in profile_data.get("accounts", [])
                ],
                "urls": profile_data.get("urls", []),
            }
        else:
            result["gravatar"] = {
                "found": False,
                "avatar_url": f"https://www.gravatar.com/avatar/{email_hash}?d=404",
                "note": "No Gravatar profile registered for this email.",
            }
    except Exception as exc:
        result["gravatar"] = {"found": False, "error": str(exc)}

    # ── HaveIBeenPwned breach lookup ─────────────────────────────
    if HIBP_API_KEY:
        try:
            hibp_headers = {
                "hibp-api-key": HIBP_API_KEY,
                "User-Agent": "NexusScope-OSINT/2.0",
            }
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                breach_resp = await client.get(
                    f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
                    headers=hibp_headers,
                    params={"truncateResponse": "false"},
                )
            if breach_resp.status_code == 200:
                breaches = breach_resp.json()
                result["breaches"] = [
                    {
                        "name": b.get("Name"),
                        "title": b.get("Title"),
                        "breach_date": b.get("BreachDate"),
                        "pwn_count": b.get("PwnCount"),
                        "description": re.sub(r"<[^>]+>", "", b.get("Description", "")),
                        "data_classes": b.get("DataClasses", []),
                        "is_sensitive": b.get("IsSensitive", False),
                        "is_verified": b.get("IsVerified", True),
                    }
                    for b in breaches
                ]
                result["breach_count"] = len(breaches)
            elif breach_resp.status_code == 404:
                result["breaches"] = []
                result["breach_count"] = 0
            else:
                result["breaches"] = None
                result["hibp_error"] = f"HIBP API returned HTTP {breach_resp.status_code}"

            # Paste check
            paste_resp = await client.get(
                f"https://haveibeenpwned.com/api/v3/pasteaccount/{email}",
                headers=hibp_headers,
            )
            if paste_resp.status_code == 200:
                pastes = paste_resp.json()
                result["pastes"] = [
                    {"source": p.get("Source"), "id": p.get("Id"), "date": p.get("Date")}
                    for p in pastes
                ]
                result["paste_count"] = len(pastes)
            elif paste_resp.status_code == 404:
                result["pastes"] = []
                result["paste_count"] = 0
        except Exception as exc:
            result["hibp_error"] = str(exc)
    else:
        result["breaches"] = None
        result["hibp_note"] = (
            "Set HIBP_API_KEY environment variable to enable breach lookup. "
            "Get a key at haveibeenpwned.com/API/Key"
        )

    # ── MX record check (validates email domain is live) ─────────
    if domain:
        try:
            resolver = dns.asyncresolver.Resolver()
            resolver.timeout = 5
            resolver.lifetime = 7
            mx_answer = await resolver.resolve(domain, "MX")
            result["mx_records"] = [
                f"{r.preference} {r.exchange}" for r in mx_answer
            ]
        except Exception:
            result["mx_records"] = []

    return result


async def _image_metadata(image_url: str, proxy: Optional[str], timeout: int) -> Dict[str, Any]:
    target = _normalize_url(image_url)
    async with _httpx_client(proxy=proxy, timeout=timeout) as client:
        response = await client.get(target)
        response.raise_for_status()
        raw = response.content
        content_type = response.headers.get("content-type", "unknown")
        size_bytes = len(raw)

    tags = {}
    try:
        tags = exifread.process_file(io.BytesIO(raw), details=False) or {}
    except Exception:
        pass

    return {
        "image_url": target,
        "content_type": content_type,
        "file_size_bytes": size_bytes,
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
    module = _normalize_module_name(str(task["module"]))
    target = str(task["target"])
    options = task.get("options", {}) or {}
    proxy = task.get("proxy")
    timeout = int(options.get("timeout", 12))
    use_playwright = bool(options.get("use_playwright", False))

    try:
        if module == "domain":
            result = await _domain_lookup(target)
            result.update(_trust_score(result))
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
        # ── Theater 1: Dark Web / Onion ──────────────────────────
        elif module == "darkweb":
            result = await _onion_crawler(target)
        # ── Theater 2: General Recon (Phone) ─────────────────────
        elif module == "phone":
            result = await _phone_lookup(target)
        # ── Theater 3: Identity & Credential Hunting ─────────────
        elif module == "email":
            result = await _email_lookup(target)
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
        error_msg = f"{type(exc).__name__}: {str(exc)}"
        logger.error(f"Investigation task failed: {error_msg}")
        async with TASK_LOCK:
            task["status"] = "failed"
            task["error"] = error_msg
            task["completed_at"] = completed_at
            task["duration_ms"] = int((completed_at - start) * 1000)


@router.post("/investigations", response_model=CreateInvestigationResponse)
async def create_investigation(payload: InvestigationRequest) -> CreateInvestigationResponse:
    module = _normalize_module_name(payload.module or payload.type or "")
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
        "execution_mode": "local",
    }

    async with TASK_LOCK:
        TASKS[task_id] = task

    asyncio.create_task(_execute_task(task_id))

    return CreateInvestigationResponse(task_id=task_id)


@router.get("/investigations/{task_id}", response_model=InvestigationStatusResponse)
async def get_investigation_status(task_id: str) -> InvestigationStatusResponse:
    async with TASK_LOCK:
        task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Investigation not found")

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
