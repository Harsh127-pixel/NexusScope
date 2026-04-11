"""
app/api/endpoints/intel.py — Legacy OSINT endpoints (§7–§10 from original main.py)

These are the original single-shot endpoints that existed before the Theater
modular system. They persist scan results directly to the osint_logs PostgreSQL
table and support optional Firebase auth.

Routes exposed:
  GET  /api/v1/intel/ip/{ip_address}        — IP geolocation + ISP
  GET  /api/v1/intel/domain/{domain}        — DNS full enumeration
  POST /api/v1/intel/forensics/image        — EXIF / GPS image forensics
  GET  /api/v1/intel/identity/{username}    — GitHub identity scrape
"""
from __future__ import annotations

import io
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import dns.asyncresolver
import exifread
import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field

from app.core.config import HTTP_TIMEOUT, USER_AGENT
from app.core.database import log_to_db
from app.core.firebase import verify_firebase_token

router = APIRouter()
logger = logging.getLogger(__name__)

_DNS_RECORD_TYPES = ["A", "MX", "NS", "TXT", "AAAA", "CNAME"]


# ── Pydantic models ───────────────────────────────────────────────────────────

class IPIntelligenceResponse(BaseModel):
    scan_id: str
    ip: str
    country: Optional[str] = None
    country_code: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    isp: Optional[str] = None
    organization: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[str] = None
    asn: Optional[str] = None
    logged_at: str


class DNSRecord(BaseModel):
    record_type: str
    values: List[str]


class DomainEnumerationResponse(BaseModel):
    scan_id: str
    domain: str
    records: List[DNSRecord]
    spf_policy: Optional[str] = None
    logged_at: str


class GPSCoordinates(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_meters: Optional[float] = None


class ImageForensicsResponse(BaseModel):
    scan_id: str
    filename: str
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    datetime_original: Optional[str] = None
    software: Optional[str] = None
    gps: Optional[GPSCoordinates] = None
    raw_tag_count: int
    logged_at: str


class IdentityTrackingResponse(BaseModel):
    scan_id: str
    username: str
    platform: str
    profile_url: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    public_repos: Optional[int] = None
    followers: Optional[int] = None
    following: Optional[int] = None
    avatar_url: Optional[str] = None
    profile_found: bool
    logged_at: str


# ── Auth dependency ───────────────────────────────────────────────────────────

async def optional_auth(request: Request) -> Optional[Dict[str, Any]]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return verify_firebase_token(auth_header.split(" ", 1)[1])
    return None


# ── §7  IP Intelligence ───────────────────────────────────────────────────────

@router.get(
    "/ip/{ip_address}",
    response_model=IPIntelligenceResponse,
    tags=["OSINT — IP Intelligence"],
    summary="Geolocate & enrich an IP address",
)
async def ip_intelligence(
    ip_address: str,
    user: Optional[Dict[str, Any]] = Depends(optional_auth),
) -> IPIntelligenceResponse:
    """Resolves an IPv4/IPv6 address via GeoJS and returns ISP, ASN, and coordinates."""
    scan_id = str(uuid.uuid4())
    logged_at = datetime.now(timezone.utc).isoformat()
    user_uid = user.get("uid") if user else None
    geo_data: Dict[str, Any] = {}

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(
                f"https://get.geojs.io/v1/ip/geo/{ip_address}.json",
                headers={"User-Agent": USER_AGENT},
            )
            resp.raise_for_status()
            geo_data = resp.json()
    except Exception as exc:
        logger.warning("IP intel error for %s: %s", ip_address, exc)

    def _safe_float(val: Any) -> Optional[float]:
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    result = IPIntelligenceResponse(
        scan_id=scan_id,
        ip=geo_data.get("ip", ip_address),
        country=geo_data.get("country"),
        country_code=geo_data.get("country_code"),
        region=geo_data.get("region"),
        city=geo_data.get("city"),
        isp=geo_data.get("isp") or geo_data.get("organization_name"),
        organization=geo_data.get("organization_name"),
        latitude=_safe_float(geo_data.get("latitude")),
        longitude=_safe_float(geo_data.get("longitude")),
        timezone=geo_data.get("timezone"),
        asn=geo_data.get("asn"),
        logged_at=logged_at,
    )
    await log_to_db("ip_intel", ip_address, scan_id, result.model_dump(), user_uid)
    return result


# ── §8  Domain Enumeration ────────────────────────────────────────────────────

@router.get(
    "/domain/{domain}",
    response_model=DomainEnumerationResponse,
    tags=["OSINT — Domain Enumeration"],
    summary="Enumerate DNS records for a domain",
)
async def domain_enumeration(
    domain: str,
    user: Optional[Dict[str, Any]] = Depends(optional_auth),
) -> DomainEnumerationResponse:
    """Multi-type async DNS resolution with SPF extraction."""
    scan_id = str(uuid.uuid4())
    logged_at = datetime.now(timezone.utc).isoformat()
    user_uid = user.get("uid") if user else None

    resolver = dns.asyncresolver.Resolver()
    resolver.timeout = 5
    resolver.lifetime = 8
    records: List[DNSRecord] = []
    spf_policy: Optional[str] = None

    for rtype in _DNS_RECORD_TYPES:
        try:
            answer = await resolver.resolve(domain, rtype)
            values: List[str] = []
            for rdata in answer:
                if rtype == "MX":
                    values.append(f"{rdata.preference} {rdata.exchange}")
                elif rtype == "TXT":
                    txt_val = " ".join(
                        part.decode("utf-8", errors="replace") if isinstance(part, bytes) else str(part)
                        for part in rdata.strings
                    )
                    values.append(txt_val)
                    if txt_val.startswith("v=spf1") and spf_policy is None:
                        spf_policy = txt_val
                else:
                    values.append(str(rdata))
            if values:
                records.append(DNSRecord(record_type=rtype, values=values))
        except dns.asyncresolver.NXDOMAIN:
            break
        except Exception as exc:
            logger.debug("DNS %s for %s: %s", rtype, domain, exc)

    result = DomainEnumerationResponse(
        scan_id=scan_id, domain=domain, records=records, spf_policy=spf_policy, logged_at=logged_at
    )
    await log_to_db("domain_enum", domain, scan_id, result.model_dump(), user_uid)
    return result


# ── §9  Image Forensics ───────────────────────────────────────────────────────

def _dms_to_decimal(dms_values: Any, ref: str) -> Optional[float]:
    try:
        d = float(dms_values.values[0].num) / float(dms_values.values[0].den)
        m = float(dms_values.values[1].num) / float(dms_values.values[1].den)
        s = float(dms_values.values[2].num) / float(dms_values.values[2].den)
        dec = d + (m / 60.0) + (s / 3600.0)
        return round(-dec if ref in ("S", "W") else dec, 7)
    except Exception:
        return None


@router.post(
    "/forensics/image",
    response_model=ImageForensicsResponse,
    tags=["OSINT — Image Forensics"],
    summary="Extract EXIF metadata and GPS from an uploaded image",
)
async def image_forensics(
    file: UploadFile = File(...),
    user: Optional[Dict[str, Any]] = Depends(optional_auth),
) -> ImageForensicsResponse:
    """In-memory EXIF extraction — no disk writes. Supports JPEG, TIFF, DNG, CR2, NEF."""
    scan_id = str(uuid.uuid4())
    logged_at = datetime.now(timezone.utc).isoformat()
    user_uid = user.get("uid") if user else None
    filename = file.filename or "unknown"

    try:
        raw_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read file: {exc}")

    tags: Dict[str, Any] = {}
    try:
        tags = exifread.process_file(io.BytesIO(raw_bytes), details=False)
    except Exception as exc:
        logger.warning("exifread error for %s: %s", filename, exc)

    def _tag(key: str) -> Optional[str]:
        val = tags.get(key)
        return str(val).strip() if val else None

    gps: Optional[GPSCoordinates] = None
    lat_dms, lat_ref = tags.get("GPS GPSLatitude"), tags.get("GPS GPSLatitudeRef")
    lon_dms, lon_ref = tags.get("GPS GPSLongitude"), tags.get("GPS GPSLongitudeRef")
    alt_tag = tags.get("GPS GPSAltitude")
    if lat_dms and lat_ref and lon_dms and lon_ref:
        altitude = None
        try:
            if alt_tag:
                altitude = round(float(alt_tag.values[0].num) / float(alt_tag.values[0].den), 2)
        except Exception:
            pass
        gps = GPSCoordinates(
            latitude=_dms_to_decimal(lat_dms, str(lat_ref)),
            longitude=_dms_to_decimal(lon_dms, str(lon_ref)),
            altitude_meters=altitude,
        )

    result = ImageForensicsResponse(
        scan_id=scan_id, filename=filename,
        camera_make=_tag("Image Make"), camera_model=_tag("Image Model"),
        datetime_original=_tag("EXIF DateTimeOriginal"), software=_tag("Image Software"),
        gps=gps, raw_tag_count=len(tags), logged_at=logged_at,
    )
    await log_to_db("image_forensics", filename, scan_id, result.model_dump(), user_uid)
    return result


# ── §10 Identity Tracking ─────────────────────────────────────────────────────

@router.get(
    "/identity/{username}",
    response_model=IdentityTrackingResponse,
    tags=["OSINT — Identity Tracking"],
    summary="Scrape public GitHub profile intelligence",
)
async def identity_tracking(
    username: str,
    user: Optional[Dict[str, Any]] = Depends(optional_auth),
) -> IdentityTrackingResponse:
    """Async BeautifulSoup scrape of github.com/{username} for public profile data."""
    scan_id = str(uuid.uuid4())
    logged_at = datetime.now(timezone.utc).isoformat()
    user_uid = user.get("uid") if user else None
    target_url = f"https://github.com/{username}"

    profile_found = False
    display_name = bio = avatar_url = None
    public_repos = followers = following = None

    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
            follow_redirects=True,
        ) as client:
            resp = await client.get(target_url)

        if resp.status_code == 200:
            profile_found = True
            soup = BeautifulSoup(resp.text, "html.parser")

            name_tag = soup.find("span", {"itemprop": "name"})
            display_name = name_tag.get_text(strip=True) if name_tag else None

            bio_tag = soup.find("div", {"data-bio-text": True}) or soup.find("div", class_=re.compile(r"p-note"))
            bio = bio_tag.get_text(strip=True) if bio_tag else None

            avatar_tag = soup.find("img", {"alt": re.compile(rf"@{re.escape(username)}", re.I)})
            avatar_url = avatar_tag["src"] if avatar_tag and avatar_tag.get("src") else None

            def _parse_count(label_text: str) -> Optional[int]:
                try:
                    for span in soup.find_all("span", class_=re.compile(r"Counter|counter")):
                        if label_text.lower() in span.parent.get_text(strip=True).lower():
                            raw = span.get_text(strip=True).replace(",", "")
                            return int(float(raw[:-1]) * 1000) if raw.endswith("k") else int(raw)
                except Exception:
                    pass
                return None

            public_repos = _parse_count("repositories") or _parse_count("repos")
            followers = _parse_count("followers")
            following = _parse_count("following")

    except Exception as exc:
        logger.error("Identity scrape error for %s: %s", username, exc)

    result = IdentityTrackingResponse(
        scan_id=scan_id, username=username, platform="GitHub", profile_url=target_url,
        display_name=display_name, bio=bio, public_repos=public_repos,
        followers=followers, following=following, avatar_url=avatar_url,
        profile_found=profile_found, logged_at=logged_at,
    )
    await log_to_db("identity", username, scan_id, result.model_dump(), user_uid)
    return result
