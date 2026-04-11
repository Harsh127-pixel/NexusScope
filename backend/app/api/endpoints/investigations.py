import asyncio
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

load_dotenv(dotenv_path=Path(__file__).resolve().parents[3] / ".env", override=False)

TASKS: Dict[str, Dict[str, Any]] = {}
TASK_LOCK = asyncio.Lock()
UA_FILE_PATH = Path(__file__).resolve().parents[2] / "data" / "user_agents.json"
_CACHED_UA: Optional[List[str]] = None
DEFAULT_SCRAPER_PROXY = os.getenv("DEFAULT_SCRAPER_PROXY")
TOR_PROXY_URL = os.getenv("TOR_PROXY_URL", "socks5://127.0.0.1:9050")
TOR_TIMEOUT = int(os.getenv("TOR_TIMEOUT", "45"))
HIBP_API_KEY = os.getenv("HIBP_API_KEY", "")
LEAKOSINT_API_URL = os.getenv("LEAKOSINT_API_URL", "https://leakosintapi.com/")
LEAKOSINT_TOKEN = os.getenv("LEAKOSINT_TOKEN", "")
LEAKOSINT_LANG = os.getenv("LEAKOSINT_LANG", "en")
LEAKOSINT_LIMIT = int(os.getenv("LEAKOSINT_LIMIT", "100"))


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
        "darkweb": "darkweb",
        "onion": "darkweb",
        "onioncrawler": "darkweb",
        "domain": "domain",
        "domains": "domain",
        "ip": "ip",
        "iplookup": "ip",
        "phone": "phone",
        "phonelookup": "phone",
        "email": "email",
        "emailhunt": "email",
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
        "deepsearch": "deepsearch",
        "leakdb": "deepsearch",
        "leakdbscan": "deepsearch",
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
        try:
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
        except Exception as exc:
            return {
                "whois_server": server,
                "domain": host,
                "error": f"whois_lookup_failed: {exc}",
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
    try:
        return await loop.run_in_executor(None, _lookup)
    except Exception as exc:
        return {
            "error": f"tls_lookup_failed: {exc}",
        }


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
        "score": score,
        "rating": rating,
        "signals": signals,
        "warnings": deductions,
        "note": "Heuristic trust score based on public signals, not a definitive fraud verdict.",
    }


def _httpx_client(proxy: Optional[str], timeout: int) -> httpx.AsyncClient:
    kwargs: Dict[str, Any] = {
        "timeout": timeout,
        "follow_redirects": True,
        "verify": False,
        "headers": {
            "User-Agent": _pick_user_agent(),
            "Accept-Language": "en-US,en;q=0.9",
        },
    }
    if proxy:
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
        return (0, "timeout")
    except Exception:
        return (0, "error")


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
        "whois": await _whois_lookup(domain),
        "subdomains": await _common_subdomains(domain) + await _crtsh_subdomains(domain),
        "tls": await _tls_metadata(domain),
        "web": await _web_fingerprint(domain),
        "s3_buckets": await _hunt_s3_buckets(domain),
    }


async def _ip_lookup(ip_addr: str) -> Dict[str, Any]:
    resolver = dns.asyncresolver.Resolver()
    ptr_result: List[str] = []
    try:
        answer = await resolver.resolve_address(ip_addr)
        ptr_result = [str(item) for item in answer]
    except Exception as exc:
        ptr_result = [f"ptr_error: {exc}"]

    geo: Dict[str, Any] = {}
    geo_error: Optional[str] = None
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers={"User-Agent": _pick_user_agent()}) as client:
            response = await client.get(f"https://ipapi.co/{ip_addr}/json/")
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict) and not payload.get("error"):
                geo = payload
            else:
                geo_error = str(payload.get("reason") or payload.get("error") or "geolocation_unavailable")
    except Exception as exc:
        geo_error = f"geolocation_lookup_failed: {exc}"

    return {
        "ip": ip_addr,
        "ptr": ptr_result,
        "country": geo.get("country_name"),
        "country_code": geo.get("country_code"),
        "region": geo.get("region"),
        "city": geo.get("city"),
        "latitude": geo.get("latitude"),
        "longitude": geo.get("longitude"),
        "timezone": geo.get("timezone"),
        "asn": geo.get("asn"),
        "organization": geo.get("org"),
        "isp": geo.get("org"),
        "network": geo.get("network"),
        "geolocation_source": "ipapi.co" if geo else None,
        "geolocation_error": geo_error,
    }


async def _check_tor_health() -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(proxy=TOR_PROXY_URL, timeout=10.0, follow_redirects=True, headers={"User-Agent": _pick_user_agent()}) as client:
            resp = await client.get("https://check.torproject.org/")
            if "Congratulations" in resp.text:
                soup = BeautifulSoup(resp.text, "lxml")
                ip_tag = soup.find("strong")
                return {
                    "tor_running": True,
                    "exit_ip": ip_tag.get_text(strip=True) if ip_tag else None,
                    "proxy_url": TOR_PROXY_URL,
                    "status": "connected",
                }
            return {
                "tor_running": False,
                "proxy_url": TOR_PROXY_URL,
                "status": "connected_but_not_tor",
            }
    except Exception as exc:
        return {
            "tor_running": False,
            "proxy_url": TOR_PROXY_URL,
            "status": "error",
            "error": str(exc),
        }


async def _ahmia_search(query: str) -> Dict[str, Any]:
    url = f"https://ahmia.fi/search/?q={query}"
    try:
        async with _httpx_client(proxy=None, timeout=20) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
    except Exception as exc:
        return {
            "is_search": True,
            "query": query,
            "url": url,
            "error": f"ahmia_search_failed: {exc}",
        }

    soup = BeautifulSoup(html, "lxml")
    results = []
    for item in soup.find_all("li"):
        cite_tag = item.find("cite")
        if not cite_tag:
            continue
        title_tag = item.find("h4") or item.find("a")
        desc_tag = item.find("p")
        onion_url = cite_tag.get_text(strip=True)
        if onion_url:
            results.append(
                {
                    "title": title_tag.get_text(strip=True) if title_tag else None,
                    "onion_url": onion_url,
                    "description": desc_tag.get_text(strip=True) if desc_tag else None,
                }
            )

    return {
        "is_search": True,
        "url": url,
        "query": query,
        "search_results": results[:25],
        "total_returned": len(results),
        "source": "ahmia.fi",
    }


async def _onion_crawler(target: str) -> Dict[str, Any]:
    if ".onion" not in target.lower() and "http" not in target.lower():
        return await _ahmia_search(target)

    onion_url = target if target.startswith("http") else f"http://{target}"
    tor_status = await _check_tor_health()
    if not tor_status.get("tor_running"):
        return {
            "url": onion_url,
            "crawl_success": False,
            "tor_status": tor_status,
            "error": "tor_proxy_unreachable",
        }

    try:
        async with httpx.AsyncClient(
            proxy=TOR_PROXY_URL,
            timeout=TOR_TIMEOUT,
            headers={"User-Agent": _pick_user_agent()},
            follow_redirects=True,
            verify=False,
        ) as client:
            response = await client.get(onion_url)
            response.raise_for_status()
            html = response.text
    except Exception as exc:
        return {
            "url": onion_url,
            "crawl_success": False,
            "tor_status": tor_status,
            "error": str(exc),
        }

    soup = BeautifulSoup(html, "lxml")
    title = soup.title.get_text(strip=True) if soup.title else None
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text_excerpt = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()[:1500]
    onion_links = list(dict.fromkeys(re.findall(r"[a-z2-7]{16,56}\.onion", html.lower())))
    emails_found = list(dict.fromkeys(re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", html)))

    return {
        "url": onion_url,
        "crawl_success": True,
        "tor_status": tor_status,
        "title": title,
        "text_excerpt": text_excerpt,
        "onion_links_discovered": onion_links[:50],
        "emails_found": emails_found[:20],
    }


async def _scrape_web(target: str, proxy: Optional[str], timeout: int, use_playwright: bool) -> Dict[str, Any]:
    url = _normalize_url(target)
    html: Optional[str] = None
    method = "httpx"
    effective_proxy = proxy

    if ".onion" in url.lower() and not effective_proxy:
        effective_proxy = TOR_PROXY_URL

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
        async with _httpx_client(proxy=effective_proxy, timeout=timeout) as client:
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
        "proxy_used": effective_proxy,
        "title": title,
        "meta_description": meta_description.get("content") if meta_description else None,
        "h1": [h.get_text(strip=True) for h in soup.find_all("h1")[:5]],
        "links_sample": links,
    }


async def _username_lookup(username: str, proxy: Optional[str], timeout: int) -> Dict[str, Any]:
    async def _github() -> Dict[str, Any]:
        url = f"https://github.com/{username}"
        try:
            async with _httpx_client(proxy=proxy, timeout=timeout) as client:
                response = await client.get(url)
            if response.status_code == 404:
                return {"platform": "github", "profile_found": False, "url": url}
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            name_tag = soup.find("span", {"itemprop": "name"})
            bio_tag = soup.find("div", class_=re.compile(r"p-note", re.I))
            return {
                "platform": "github",
                "profile_found": True,
                "url": url,
                "display_name": name_tag.get_text(strip=True) if name_tag else None,
                "bio": bio_tag.get_text(strip=True) if bio_tag else None,
            }
        except Exception as exc:
            return {"platform": "github", "profile_found": False, "url": url, "error": str(exc)}

    async def _reddit() -> Dict[str, Any]:
        url = f"https://www.reddit.com/user/{username}/about.json"
        try:
            async with _httpx_client(proxy=proxy, timeout=timeout) as client:
                response = await client.get(url, headers={"User-Agent": _pick_user_agent()})
            if response.status_code == 404:
                return {"platform": "reddit", "profile_found": False, "url": f"https://www.reddit.com/user/{username}"}
            response.raise_for_status()
            payload = response.json().get("data", {})
            return {
                "platform": "reddit",
                "profile_found": True,
                "url": f"https://www.reddit.com/user/{username}",
                "display_name": payload.get("subreddit", {}).get("title") or payload.get("name"),
                "karma": payload.get("total_karma"),
                "created_utc": payload.get("created_utc"),
            }
        except Exception as exc:
            return {"platform": "reddit", "profile_found": False, "url": f"https://www.reddit.com/user/{username}", "error": str(exc)}

    async def _hn() -> Dict[str, Any]:
        url = f"https://hn.algolia.com/api/v1/users/{username}"
        try:
            async with _httpx_client(proxy=proxy, timeout=timeout) as client:
                response = await client.get(url)
            if response.status_code == 404:
                return {"platform": "hackernews", "profile_found": False, "url": f"https://news.ycombinator.com/user?id={username}"}
            response.raise_for_status()
            payload = response.json()
            return {
                "platform": "hackernews",
                "profile_found": True,
                "url": f"https://news.ycombinator.com/user?id={username}",
                "display_name": payload.get("username"),
                "karma": payload.get("karma"),
                "about": payload.get("about"),
                "created_at": payload.get("created_at"),
            }
        except Exception as exc:
            return {"platform": "hackernews", "profile_found": False, "url": f"https://news.ycombinator.com/user?id={username}", "error": str(exc)}

    async def _x() -> Dict[str, Any]:
        url = f"https://x.com/{username}"
        try:
            async with _httpx_client(proxy=proxy, timeout=timeout) as client:
                response = await client.get(url)
            return {
                "platform": "x",
                "profile_found": response.status_code not in {404},
                "url": url,
                "status_code": response.status_code,
                "note": "X/Twitter pages often challenge bots; status_code is advisory.",
            }
        except Exception as exc:
            return {"platform": "x", "profile_found": False, "url": url, "error": str(exc)}

    profiles = await asyncio.gather(_github(), _reddit(), _hn(), _x())
    return {
        "username": username,
        "profiles": profiles,
        "platforms_checked": [item.get("platform") for item in profiles],
        "profiles_found": sum(1 for item in profiles if item.get("profile_found")),
    }


async def _phone_lookup(phone: str) -> Dict[str, Any]:
    try:
        import importlib
        phonenumbers = importlib.import_module("phonenumbers")
        carrier = importlib.import_module("phonenumbers.carrier")
        geocoder = importlib.import_module("phonenumbers.geocoder")
        phone_tz = importlib.import_module("phonenumbers.timezone")
    except Exception as exc:
        return {
            "phone": phone,
            "error": f"phonenumbers_not_available: {exc}",
            "note": "Install phonenumbers to enable carrier and line-type enrichment.",
        }

    try:
        parsed = phonenumbers.parse(phone, None)
    except Exception as exc:
        return {
            "phone": phone,
            "error": f"phone_parse_failed: {exc}",
        }

    phone_number_type = phonenumbers.PhoneNumberType
    number_type_map = {
        phone_number_type.MOBILE: "mobile",
        phone_number_type.FIXED_LINE: "fixed_line",
        phone_number_type.FIXED_LINE_OR_MOBILE: "fixed_or_mobile",
        phone_number_type.TOLL_FREE: "toll_free",
        phone_number_type.PREMIUM_RATE: "premium_rate",
        phone_number_type.VOIP: "voip",
        phone_number_type.PAGER: "pager",
        phone_number_type.UAN: "uan",
        phone_number_type.VOICEMAIL: "voicemail",
        phone_number_type.SHARED_COST: "shared_cost",
        phone_number_type.PERSONAL_NUMBER: "personal_number",
        phone_number_type.UNKNOWN: "unknown",
    }

    nt = phonenumbers.number_type(parsed)
    return {
        "phone": phone,
        "valid": phonenumbers.is_valid_number(parsed),
        "possible": phonenumbers.is_possible_number(parsed),
        "e164": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164),
        "international": phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
        "country_code": parsed.country_code,
        "country": geocoder.description_for_number(parsed, "en"),
        "carrier": carrier.name_for_number(parsed, "en"),
        "line_type": number_type_map.get(nt, "unknown"),
        "timezones": list(phone_tz.time_zones_for_number(parsed)),
        "source": "python-phonenumbers",
    }


async def _email_lookup(email: str, timeout: int) -> Dict[str, Any]:
    normalized = email.strip().lower()
    hash_md5 = hashlib.md5(normalized.encode("utf-8")).hexdigest()
    gravatar_profile_url = f"https://www.gravatar.com/{hash_md5}.json"
    gravatar_avatar_url = f"https://www.gravatar.com/avatar/{hash_md5}?d=404&s=256"

    gravatar: Dict[str, Any] = {
        "profile_found": False,
        "avatar_found": False,
        "profile_url": gravatar_profile_url,
        "avatar_url": gravatar_avatar_url,
    }

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": _pick_user_agent()}) as client:
        try:
            prof = await client.get(gravatar_profile_url)
            if prof.status_code == 200:
                data = prof.json()
                entries = data.get("entry", []) if isinstance(data, dict) else []
                entry = entries[0] if entries else {}
                gravatar.update(
                    {
                        "profile_found": True,
                        "display_name": entry.get("displayName"),
                        "about_me": entry.get("aboutMe"),
                        "thumbnail_url": entry.get("thumbnailUrl"),
                        "profile_urls": entry.get("urls", []),
                    }
                )
        except Exception as exc:
            gravatar["profile_error"] = str(exc)

        try:
            avatar = await client.get(gravatar_avatar_url)
            gravatar["avatar_found"] = avatar.status_code == 200
        except Exception as exc:
            gravatar["avatar_error"] = str(exc)

    hibp: Dict[str, Any] = {
        "checked": False,
        "breaches": [],
        "count": 0,
    }

    if HIBP_API_KEY:
        hibp_url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{normalized}"
        headers = {
            "hibp-api-key": HIBP_API_KEY,
            "user-agent": "NexusScope/1.0",
        }
        try:
            async with httpx.AsyncClient(timeout=max(timeout, 15), follow_redirects=True) as client:
                resp = await client.get(hibp_url, params={"truncateResponse": "false"}, headers=headers)
            if resp.status_code == 404:
                hibp.update({"checked": True, "breaches": [], "count": 0})
            elif resp.status_code == 200:
                breaches = resp.json()
                hibp.update({"checked": True, "breaches": breaches, "count": len(breaches) if isinstance(breaches, list) else 0})
            else:
                hibp.update({"checked": True, "error": f"hibp_http_{resp.status_code}"})
        except Exception as exc:
            hibp.update({"checked": True, "error": str(exc)})
    else:
        hibp["note"] = "HIBP_API_KEY is not configured. Set it in backend/.env to enable breach checks."

    return {
        "email": normalized,
        "gravatar": gravatar,
        "hibp": hibp,
    }


async def _deepsearch_lookup(target: str, limit: Optional[int], lang: Optional[str]) -> Dict[str, Any]:
    if not LEAKOSINT_TOKEN:
        return {
            "query": target,
            "error": "missing_leakosint_token",
            "note": "Set LEAKOSINT_TOKEN in backend/.env to enable deep search.",
        }

    payload = {
        "token": LEAKOSINT_TOKEN,
        "request": target,
        "limit": int(limit or LEAKOSINT_LIMIT),
        "lang": lang or LEAKOSINT_LANG,
        "type": "json",
    }

    async with httpx.AsyncClient(timeout=40.0, follow_redirects=True, headers={"User-Agent": _pick_user_agent()}) as client:
        response = await client.post(LEAKOSINT_API_URL, json=payload)
        response.raise_for_status()
        raw = response.json()

    if isinstance(raw, dict) and raw.get("Error code"):
        return {
            "query": target,
            "error": f"leakosint_error: {raw.get('Error code')}",
            "raw": raw,
        }

    dbs = []
    total_records = 0
    for db_name, db_data in (raw.get("List", {}) if isinstance(raw, dict) else {}).items():
        records = db_data.get("Data", []) if isinstance(db_data, dict) else []
        total_records += len(records)
        dbs.append(
            {
                "database": db_name,
                "count": len(records),
                "records": records[:50],
                "info": db_data.get("InfoLeak", "") if isinstance(db_data, dict) else "",
            }
        )

    dbs.sort(key=lambda item: item["count"], reverse=True)

    return {
        "module": "deepsearch",
        "query": target,
        "limit": payload["limit"],
        "lang": payload["lang"],
        "total_records": total_records,
        "databases_hit": sum(1 for item in dbs if item["count"] > 0),
        "databases": dbs,
    }


async def _image_metadata(image_url: str, proxy: Optional[str], timeout: int) -> Dict[str, Any]:
    target = _normalize_url(image_url)
    headers = {
        "User-Agent": _pick_user_agent(),
        "Referer": "https://www.google.com/",
    }

    try:
        async with _httpx_client(proxy=proxy, timeout=timeout) as client:
            response = await client.get(target, headers=headers)
            response.raise_for_status()
            raw = response.content
    except Exception as exc:
        return {
            "image_url": target,
            "tag_count": 0,
            "error": f"image_fetch_failed: {exc}",
        }

    try:
        tags = exifread.process_file(io.BytesIO(raw), details=False)
    except Exception as exc:
        return {
            "image_url": target,
            "tag_count": 0,
            "error": f"exif_parse_failed: {exc}",
        }

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
    module = _normalize_module_name(str(task["module"]))
    target = str(task["target"])
    options = task.get("options", {}) or {}
    proxy = task.get("proxy")
    timeout = int(options.get("timeout", 12))
    use_playwright = bool(options.get("use_playwright", False))
    deepsearch_limit = options.get("limit")
    deepsearch_lang = options.get("lang")

    try:
        if module == "darkweb":
            result = await _onion_crawler(target)
        elif module == "domain":
            result = await _domain_lookup(target)
            result["trust"] = _trust_score(result)
        elif module == "ip":
            result = await _ip_lookup(target)
        elif module == "phone":
            result = await _phone_lookup(target)
        elif module == "email":
            result = await _email_lookup(target, timeout=timeout)
        elif module == "username":
            result = await _username_lookup(target, proxy=proxy, timeout=timeout)
        elif module == "metadata":
            result = await _image_metadata(target, proxy=proxy, timeout=timeout)
        elif module == "deepsearch":
            result = await _deepsearch_lookup(target, deepsearch_limit, deepsearch_lang)
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
