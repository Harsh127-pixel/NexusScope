"""
╔══════════════════════════════════════════════════════════════════════════════╗
║          IntrusionX SE  —  Industrial-Grade OSINT Aggregation Engine        ║
║          Principal Architect: NexusScope Security Team                      ║
║          Stack: FastAPI · asyncpg · Firebase Admin · httpx · dnspython      ║
╚══════════════════════════════════════════════════════════════════════════════╝

INTERNAL MODULE LAYOUT
──────────────────────
 §1  Imports & environment configuration
 §2  Pydantic response & request models
 §3  Firebase Admin SDK initialisation
 §4  PostgreSQL async connection pool
 §5  FastAPI application factory & middleware
 §6  Dependency helpers (auth guard, db session)
 §7  OSINT Module A  – IP Intelligence
 §8  OSINT Module B  – Domain Enumeration
 §9  OSINT Module C  – Image Forensics (ExifRead + GPS)
 §10 OSINT Module D  – Identity / Username Tracking
 §11 Chatbot Module  – Telegram webhook
 §12 Chatbot Module  – WhatsApp webhook (Meta verification + inbound)
 §13 Application lifecycle (startup / shutdown)
 §14 Entrypoint (uvicorn)
"""

# ──────────────────────────────────────────────
# §1  IMPORTS & ENVIRONMENT
# ──────────────────────────────────────────────
from __future__ import annotations

import io
import logging
import math
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Third-party — installed via requirements.txt
import asyncpg
import dns.asyncresolver
import exifread
import firebase_admin
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials
from pydantic import BaseModel, Field
from app.api.endpoints.investigations import router as investigations_router

# ── S3 Leak Hunting Module ────────────────────
from database import initialize_pool, close_pool, get_scan
from workers import run_leak_scan

# ── Logging ───────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("intrusion_x_se")

# ── Load .env automatically (local dev) ───────
#    In Docker / production, env vars are injected by the container runtime.
#    load_dotenv() is a no-op when variables are already present in the environment,
#    so it is safe to call unconditionally.
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"), override=False)

# ── App ───────────────────────────────────────
APP_NAME: str = os.environ.get("APP_NAME", "IntrusionX SE")
APP_VERSION: str = os.environ.get("APP_VERSION", "2.0.0")
DEBUG: bool = os.environ.get("DEBUG", "True").lower() == "true"

# ── Server ───────────────────────────────────
API_HOST: str = os.environ.get("API_HOST", "127.0.0.1")
API_PORT: int = int(os.environ.get("API_PORT", "8000"))

# ── PostgreSQL ────────────────────────────────
DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://osint_user:osint_pass@localhost:5432/intrusion_x_db",
)

# ── Firebase Admin SDK ────────────────────────
FIREBASE_CRED_PATH: str = os.environ.get(
    "FIREBASE_CRED_PATH",
    "/etc/secrets/firebase-service-account.json",
)
FIREBASE_PROJECT_ID: str = os.environ.get("FIREBASE_PROJECT_ID", "intrusion-x-se-default")

# ── Chatbot Tokens ────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "REPLACE_WITH_BOT_TOKEN")
WHATSAPP_VERIFY_TOKEN: str = os.environ.get("WHATSAPP_VERIFY_TOKEN", "REPLACE_WITH_VERIFY_TOKEN")
WHATSAPP_ACCESS_TOKEN: str = os.environ.get("WHATSAPP_ACCESS_TOKEN", "REPLACE_WITH_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID: str = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "REPLACE_WITH_PHONE_ID")

# ── Tuning & CORS ─────────────────────────────
HTTP_TIMEOUT: float = float(os.environ.get("HTTP_TIMEOUT", "12.0"))
USER_AGENT: str = os.environ.get("USER_AGENT", f"{APP_NAME}/{APP_VERSION} (OSINT Engine)")
# Add specific Vercel and local origins for production security
CORS_ORIGINS: str = os.environ.get("CORS_ORIGINS", "https://nexusscope.vercel.app,https://nexusscope.gaurangjadoun.in,http://localhost:5173,https://nexusscope.onrender.com")
PLAYWRIGHT_HEADLESS: bool = os.environ.get("PLAYWRIGHT_HEADLESS", "True").lower() == "true"


# ──────────────────────────────────────────────
# §2  PYDANTIC MODELS
#     All response bodies are typed — Swagger UI will render them automatically.
# ──────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str = Field(..., example="healthy")
    service: str = Field(..., example=APP_NAME)
    version: str = Field(..., example=APP_VERSION)
    timestamp: str


class IPIntelligenceResponse(BaseModel):
    """Enriched geolocation and ISP data for a given IPv4/IPv6 address."""
    scan_id: str = Field(..., description="Unique UUID for this scan result")
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
    """Comprehensive DNS enumeration result including SPF policy extraction."""
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
    """EXIF metadata and GPS forensics extracted from an uploaded image."""
    scan_id: str
    filename: str
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    datetime_original: Optional[str] = None
    software: Optional[str] = None
    gps: Optional[GPSCoordinates] = None
    raw_tag_count: int = Field(..., description="Total number of EXIF tags found")
    logged_at: str


class IdentityTrackingResponse(BaseModel):
    """Public profile intelligence gathered for a given username."""
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


class TelegramWebhookAck(BaseModel):
    status: str = "accepted"
    message: str


class WhatsAppVerifyResponse(BaseModel):
    challenge: str


# ──────────────────────────────────────────────
# S3 LEAK HUNTING MODULE — REQUEST & RESPONSE
# ──────────────────────────────────────────────

class S3LeakScanRequest(BaseModel):
    """Request model for initiating an S3 bucket leak scan."""
    domain: str = Field(..., example="example.com", description="Target domain to scan for S3 buckets")
    
    class Config:
        json_schema_extra = {
            "example": {
                "domain": "example.com"
            }
        }


class S3BucketFinding(BaseModel):
    """A single S3 bucket finding."""
    bucket_name: str
    http_code: int = Field(..., description="HTTP response code (200=open, 403=closed)")


class S3ScanResults(BaseModel):
    """Complete S3 leak scan results."""
    domain: str
    base_name: str
    total_checked: int = Field(..., description="Total bucket candidates probed")
    buckets_found: Dict[str, List[S3BucketFinding]] = Field(
        ...,
        description="Buckets grouped by status: 'open' (200 OK) and 'closed' (403 Forbidden)"
    )
    errors: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Errors grouped by type: 'timeout', 'connection_failed', etc."
    )


class S3ScanStatusResponse(BaseModel):
    """S3 leak scan status and results."""
    task_id: str = Field(..., description="UUID of the scan task")
    target_domain: str
    status: str = Field(
        ...,
        description="Current status: 'running', 'completed', or 'failed'",
        pattern="^(running|completed|failed)$"
    )
    results: Optional[S3ScanResults] = Field(None, description="Results (populated when status='completed')")
    error: Optional[str] = Field(None, description="Error message (populated when status='failed')")


class S3ScanInitResponse(BaseModel):
    """Response when starting a new S3 leak scan."""
    task_id: str = Field(..., description="UUID for tracking this scan")
    message: str
    estimated_duration_seconds: int = Field(
        default=60,
        description="Estimated time to complete scan (depends on network)"
    )


# ──────────────────────────────────────────────
# §3  FIREBASE ADMIN SDK INITIALISATION
# ──────────────────────────────────────────────

_firebase_app: Optional[firebase_admin.App] = None


def _init_firebase() -> None:
    """
    Initialise the Firebase Admin SDK singleton.

    In production, supply a valid service-account JSON at FIREBASE_CRED_PATH.
    If the credential file does not exist (e.g., local dev), the SDK is
    initialised with Application Default Credentials (ADC) as a fallback.
    The server will still start — auth-guarded routes will simply return 503
    if Firebase is unreachable.
    """
    global _firebase_app
    try:
        if os.path.exists(FIREBASE_CRED_PATH):
            cred = credentials.Certificate(FIREBASE_CRED_PATH)
            logger.info("Firebase: loading service-account from %s", FIREBASE_CRED_PATH)
        else:
            cred = credentials.ApplicationDefault()
            logger.warning(
                "Firebase: credential file not found at %s — falling back to ADC.",
                FIREBASE_CRED_PATH,
            )
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin SDK initialised successfully.")
    except Exception as exc:
        logger.error("Firebase initialisation FAILED: %s", exc)
        _firebase_app = None


def verify_firebase_token(token: str) -> Dict[str, Any]:
    """
    Verify a Firebase ID token and return the decoded claims.
    Raises HTTPException 401 on invalid/expired tokens.
    Raises HTTPException 503 if Firebase SDK is not available.
    """
    if _firebase_app is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is currently unavailable.",
        )
    try:
        decoded = firebase_auth.verify_id_token(token, app=_firebase_app)
        return decoded
    except firebase_auth.ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Firebase token has expired.")
    except firebase_auth.InvalidIdTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid Firebase token: {exc}")
    except Exception as exc:
        logger.error("Firebase token verification error: %s", exc)
        raise HTTPException(status_code=401, detail="Token verification failed.")


# ──────────────────────────────────────────────
# §4  POSTGRESQL ASYNC CONNECTION POOL
# ──────────────────────────────────────────────

_db_pool: Optional[asyncpg.Pool] = None

# DDL executed once on startup — idempotent via IF NOT EXISTS
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS osint_logs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id       UUID NOT NULL,
    module        TEXT NOT NULL,           -- 'ip_intel' | 'domain_enum' | 'image_forensics' | 'identity'
    target        TEXT NOT NULL,           -- IP, domain, username, filename
    result_json   JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_uid      TEXT                     -- Firebase UID if authenticated
);

CREATE INDEX IF NOT EXISTS idx_osint_logs_module  ON osint_logs (module);
CREATE INDEX IF NOT EXISTS idx_osint_logs_target  ON osint_logs (target);
CREATE INDEX IF NOT EXISTS idx_osint_logs_created ON osint_logs (created_at DESC);
"""


async def _init_db() -> None:
    """
    Create the asyncpg connection pool and apply the schema.
    Supports SSL for managed databases like Firebase Data Connect (Cloud SQL).
    The server starts even if PostgreSQL is unreachable — endpoints will
    return 503 for DB operations while gracefully degrading.
    """
    global _db_pool
    try:
        # For Firebase Data Connect (Cloud SQL), SSL is typically required.
        # We allow passing sslmode=require in the DSN, or we can force it here.
        ssl_ctx = False
        if "sslmode=require" in DATABASE_URL or "sslmode=verify-full" in DATABASE_URL:
            import ssl
            ssl_ctx = ssl.create_default_context()
            # If using self-signed certs (common in some internal environments), 
            # you might need to disable verification:
            # ssl_ctx.check_hostname = False
            # ssl_ctx.verify_mode = ssl.CERT_NONE

        _db_pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30,
            ssl=ssl_ctx if ssl_ctx else None,
            statement_cache_size=0,   # required for PgBouncer compatibility
        )
        async with _db_pool.acquire() as conn:
            await conn.execute(_SCHEMA_SQL)
        logger.info("PostgreSQL pool created (SSL=%s) and schema applied.", bool(ssl_ctx))
    except Exception as exc:
        logger.error("PostgreSQL pool initialisation FAILED: %s", exc)
        _db_pool = None
        _db_pool = None


async def _log_to_db(
    module: str,
    target: str,
    scan_id: str,
    result: Dict[str, Any],
    user_uid: Optional[str] = None,
) -> None:
    """
    Fire-and-forget INSERT into osint_logs.
    Designed to be awaited directly; wrap in asyncio.create_task for full
    background execution.
    """
    if _db_pool is None:
        logger.warning("DB pool unavailable — skipping log for scan_id=%s", scan_id)
        return
    try:
        import json

        async with _db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO osint_logs (scan_id, module, target, result_json, user_uid)
                VALUES ($1, $2, $3, $4::jsonb, $5)
                """,
                uuid.UUID(scan_id),
                module,
                target,
                json.dumps(result),
                user_uid,
            )
        logger.info("DB: logged scan_id=%s module=%s target=%s", scan_id, module, target)
    except Exception as exc:
        logger.error("DB insert failed for scan_id=%s: %s", scan_id, exc)


# ──────────────────────────────────────────────
# §5  FASTAPI APPLICATION FACTORY & MIDDLEWARE
# ──────────────────────────────────────────────

app = FastAPI(
    title=f"{APP_NAME} — OSINT Aggregation Engine",
    version=APP_VERSION,
    debug=DEBUG,
    description=(
        f"**{APP_NAME}** is an industrial-grade, asynchronous OSINT aggregation platform "
        "providing IP intelligence, domain enumeration, image forensics, identity tracking, "
        "and chatbot webhook integrations.\n\n"
        "### Authentication\n"
        "Protected endpoints require a Firebase ID token in the `Authorization: Bearer <token>` header.\n\n"
        "### Rate Limiting\n"
        "Apply an API gateway (e.g., Kong, Nginx) upstream. No built-in rate limiting in this layer.\n\n"
        "### Database\n"
        "All scan results are durably persisted to PostgreSQL (`osint_logs` table)."
    ),
    contact={
        "name": "NexusScope Security Team",
        "url": "https://github.com/Harsh127-pixel/NexusScope",
    },
    license_info={"name": "MIT"},
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS — Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(investigations_router, prefix="/api/v1", tags=["Investigations"])


# ──────────────────────────────────────────────
# §6  DEPENDENCY HELPERS
# ──────────────────────────────────────────────

async def get_db_pool() -> asyncpg.Pool:
    """FastAPI dependency — injects the global DB pool or raises 503."""
    if _db_pool is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is currently unavailable. Please try again later.",
        )
    return _db_pool


async def optional_auth(request: Request) -> Optional[Dict[str, Any]]:
    """
    Optional Firebase auth dependency.
    Returns decoded token claims if a valid Bearer token is provided,
    otherwise returns None (public anonymous access).
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        return verify_firebase_token(token)
    return None


async def require_auth(request: Request) -> Dict[str, Any]:
    """
    Mandatory Firebase auth dependency.
    Raises HTTP 401 if no valid token is provided.
    Attach to sensitive endpoints.
    """
    claims = await optional_auth(request)
    if claims is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid Firebase Bearer token is required for this endpoint.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return claims


# ──────────────────────────────────────────────
# §7  OSINT MODULE A — IP INTELLIGENCE
# ──────────────────────────────────────────────

@app.get(
    "/api/v1/intel/ip/{ip_address}",
    response_model=IPIntelligenceResponse,
    tags=["OSINT — IP Intelligence"],
    summary="Geolocate & enrich an IP address",
    response_description="Returns ISP, ASN, coordinates, and regional data for the target IP.",
)
async def ip_intelligence(
    ip_address: str,
    user: Optional[Dict[str, Any]] = Depends(optional_auth),
) -> IPIntelligenceResponse:
    """
    ## IP Intelligence Lookup

    Resolves an IPv4 or IPv6 address against the **GeoJS** public geolocation API
    and enriches the result with ISP, ASN, and coordinate data.

    All results are asynchronously persisted to the `osint_logs` PostgreSQL table.

    ### Parameters
    - **ip_address**: Target IPv4 or IPv6 address (e.g., `8.8.8.8`)
    """
    scan_id = str(uuid.uuid4())
    logged_at = datetime.now(timezone.utc).isoformat()
    user_uid = user.get("uid") if user else None

    geo_data: Dict[str, Any] = {}
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(
                f"https://get.geojs.io/v1/ip/geo/{ip_address}.json",
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            geo_data = response.json()
    except httpx.TimeoutException:
        logger.warning("IP intel: timeout fetching geo data for %s", ip_address)
    except httpx.HTTPStatusError as exc:
        logger.error("IP intel: HTTP %s for %s — %s", exc.response.status_code, ip_address, exc)
    except Exception as exc:
        logger.error("IP intel: unexpected error for %s — %s", ip_address, exc)

    # Parse latitude / longitude safely
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

    # Async DB insert (non-blocking — runs concurrently with response serialisation)
    await _log_to_db(
        module="ip_intel",
        target=ip_address,
        scan_id=scan_id,
        result=result.model_dump(),
        user_uid=user_uid,
    )

    return result


# ──────────────────────────────────────────────
# §8  OSINT MODULE B — DOMAIN ENUMERATION
# ──────────────────────────────────────────────

_DNS_RECORD_TYPES = ["A", "MX", "NS", "TXT", "AAAA", "CNAME"]


@app.get(
    "/api/v1/intel/domain/{domain}",
    response_model=DomainEnumerationResponse,
    tags=["OSINT — Domain Enumeration"],
    summary="Enumerate DNS records for a domain",
    response_description="Returns A, MX, NS, TXT, AAAA records along with SPF policy extraction.",
)
async def domain_enumeration(
    domain: str,
    user: Optional[Dict[str, Any]] = Depends(optional_auth),
) -> DomainEnumerationResponse:
    """
    ## Domain DNS Enumeration

    Performs asynchronous multi-type DNS resolution against the system resolver
    (or a configured upstream DNS) using **dnspython**'s async API.

    Resolved record types: `A`, `MX`, `NS`, `TXT`, `AAAA`, `CNAME`.

    **SPF detection:** TXT records are scanned for `v=spf1` directives and
    the full policy string is extracted and returned separately.

    ### Parameters
    - **domain**: Target domain or subdomain (e.g., `example.com`, `mail.google.com`)
    """
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
                        part.decode("utf-8", errors="replace")
                        if isinstance(part, bytes)
                        else str(part)
                        for part in rdata.strings
                    )
                    values.append(txt_val)
                    # Extract SPF policy
                    if txt_val.startswith("v=spf1") and spf_policy is None:
                        spf_policy = txt_val
                else:
                    values.append(str(rdata))
            if values:
                records.append(DNSRecord(record_type=rtype, values=values))
        except dns.asyncresolver.NoAnswer:
            logger.debug("Domain enum: no %s records for %s", rtype, domain)
        except dns.asyncresolver.NXDOMAIN:
            logger.warning("Domain enum: NXDOMAIN for %s", domain)
            break   # Domain does not exist — stop querying
        except dns.exception.Timeout:
            logger.warning("Domain enum: DNS timeout for %s type=%s", domain, rtype)
        except Exception as exc:
            logger.error("Domain enum: error for %s type=%s — %s", domain, rtype, exc)

    result = DomainEnumerationResponse(
        scan_id=scan_id,
        domain=domain,
        records=records,
        spf_policy=spf_policy,
        logged_at=logged_at,
    )

    await _log_to_db(
        module="domain_enum",
        target=domain,
        scan_id=scan_id,
        result=result.model_dump(),
        user_uid=user_uid,
    )

    return result


# ──────────────────────────────────────────────
# §9  OSINT MODULE C — IMAGE FORENSICS
# ──────────────────────────────────────────────

def _dms_to_decimal(dms_values: Any, ref: str) -> Optional[float]:
    """
    Convert a GPS DMS (Degrees/Minutes/Seconds) EXIF value to decimal degrees.

    Args:
        dms_values: IfdTag ratio list from exifread (D, M, S)
        ref: Cardinal direction string ('N', 'S', 'E', 'W')

    Returns:
        Decimal degree float, or None if conversion fails.
    """
    try:
        d = float(dms_values.values[0].num) / float(dms_values.values[0].den)
        m = float(dms_values.values[1].num) / float(dms_values.values[1].den)
        s = float(dms_values.values[2].num) / float(dms_values.values[2].den)
        decimal = d + (m / 60.0) + (s / 3600.0)
        if ref in ("S", "W"):
            decimal = -decimal
        return round(decimal, 7)
    except Exception:
        return None


@app.post(
    "/api/v1/intel/forensics/image",
    response_model=ImageForensicsResponse,
    tags=["OSINT — Image Forensics"],
    summary="Extract EXIF metadata and GPS coordinates from an image",
    response_description="Returns camera metadata, datetime, software fingerprint, and GPS location if embedded.",
)
async def image_forensics(
    file: UploadFile = File(..., description="JPEG/TIFF/PNG image to analyse"),
    user: Optional[Dict[str, Any]] = Depends(optional_auth),
) -> ImageForensicsResponse:
    """
    ## Image Forensics — EXIF Extraction

    Reads an uploaded image **entirely in-memory** (no disk writes) and
    uses **exifread** to parse all embedded EXIF metadata.

    ### Extracted fields
    | Field | EXIF Tag |
    |---|---|
    | Camera Make | `Image Make` |
    | Camera Model | `Image Model` |
    | Original DateTime | `EXIF DateTimeOriginal` |
    | Software | `Image Software` |
    | GPS Latitude | `GPS GPSLatitude` + `GPS GPSLatitudeRef` |
    | GPS Longitude | `GPS GPSLongitude` + `GPS GPSLongitudeRef` |
    | GPS Altitude | `GPS GPSAltitude` |

    ### Security note
    This endpoint does **not** persist raw binary content. Only extracted
    metadata JSON is written to `osint_logs`.

    ### Supported formats
    JPEG, TIFF, DNG, CR2, NEF (any format supported by exifread).
    """
    scan_id = str(uuid.uuid4())
    logged_at = datetime.now(timezone.utc).isoformat()
    user_uid = user.get("uid") if user else None
    filename = file.filename or "unknown"

    # Read file to memory — no disk I/O
    try:
        raw_bytes = await file.read()
    except Exception as exc:
        logger.error("Image forensics: failed to read upload — %s", exc)
        raise HTTPException(status_code=400, detail=f"Could not read uploaded file: {exc}")

    tags: Dict[str, Any] = {}
    try:
        image_buffer = io.BytesIO(raw_bytes)
        tags = exifread.process_file(image_buffer, details=False)
    except Exception as exc:
        logger.error("Image forensics: exifread error for %s — %s", filename, exc)
        # Graceful degradation — return empty forensics rather than 500

    # Helper to extract tag value safely
    def _tag(key: str) -> Optional[str]:
        val = tags.get(key)
        return str(val).strip() if val else None

    # GPS parsing
    gps: Optional[GPSCoordinates] = None
    lat_dms = tags.get("GPS GPSLatitude")
    lat_ref = tags.get("GPS GPSLatitudeRef")
    lon_dms = tags.get("GPS GPSLongitude")
    lon_ref = tags.get("GPS GPSLongitudeRef")
    alt_tag = tags.get("GPS GPSAltitude")

    if lat_dms and lat_ref and lon_dms and lon_ref:
        latitude = _dms_to_decimal(lat_dms, str(lat_ref))
        longitude = _dms_to_decimal(lon_dms, str(lon_ref))
        altitude: Optional[float] = None
        try:
            if alt_tag:
                altitude = round(
                    float(alt_tag.values[0].num) / float(alt_tag.values[0].den), 2
                )
        except Exception:
            pass
        gps = GPSCoordinates(latitude=latitude, longitude=longitude, altitude_meters=altitude)

    result = ImageForensicsResponse(
        scan_id=scan_id,
        filename=filename,
        camera_make=_tag("Image Make"),
        camera_model=_tag("Image Model"),
        datetime_original=_tag("EXIF DateTimeOriginal"),
        software=_tag("Image Software"),
        gps=gps,
        raw_tag_count=len(tags),
        logged_at=logged_at,
    )

    await _log_to_db(
        module="image_forensics",
        target=filename,
        scan_id=scan_id,
        result=result.model_dump(),
        user_uid=user_uid,
    )

    return result


# ──────────────────────────────────────────────
# §10 OSINT MODULE D — IDENTITY TRACKING
# ──────────────────────────────────────────────

@app.get(
    "/api/v1/intel/identity/{username}",
    response_model=IdentityTrackingResponse,
    tags=["OSINT — Identity Tracking"],
    summary="Scrape public profile intelligence for a username",
    response_description="Returns scraped public profile data from GitHub.",
)
async def identity_tracking(
    username: str,
    user: Optional[Dict[str, Any]] = Depends(optional_auth),
) -> IdentityTrackingResponse:
    """
    ## Identity / Username Intelligence

    Performs an asynchronous HTTP scrape of `github.com/{username}` using
    **httpx** + **BeautifulSoup4** to extract publicly visible profile metadata.

    ### Data points collected
    - Display name
    - Bio / description
    - Public repository count
    - Follower / following counts
    - Avatar URL

    ### Playwright skeleton (commented out)
    A full Playwright async scraping skeleton is included in the source for
    platforms that require JavaScript rendering (e.g., LinkedIn, Twitter).
    Uncomment and extend for JS-heavy targets.

    ### Parameters
    - **username**: Case-insensitive GitHub username (e.g., `torvalds`)

    ### Legal notice
    Only scrape publicly accessible data. Respect robots.txt and platform ToS.
    """
    scan_id = str(uuid.uuid4())
    logged_at = datetime.now(timezone.utc).isoformat()
    user_uid = user.get("uid") if user else None
    target_url = f"https://github.com/{username}"

    profile_found = False
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    public_repos: Optional[int] = None
    followers: Optional[int] = None
    following: Optional[int] = None

    # ── BeautifulSoup4 scrape ─────────────────
    try:
        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT,
            headers={
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
            },
            follow_redirects=True,
        ) as client:
            resp = await client.get(target_url)

        if resp.status_code == 200:
            profile_found = True
            soup = BeautifulSoup(resp.text, "html.parser")

            # Display name
            name_tag = soup.find("span", {"itemprop": "name"})
            display_name = name_tag.get_text(strip=True) if name_tag else None

            # Bio
            bio_tag = soup.find("div", {"data-bio-text": True}) or \
                      soup.find("div", class_=re.compile(r"p-note"))
            if bio_tag:
                bio = bio_tag.get_text(strip=True) or None

            # Avatar
            avatar_tag = soup.find("img", {"alt": re.compile(rf"@{re.escape(username)}", re.I)})
            if avatar_tag and avatar_tag.get("src"):
                avatar_url = avatar_tag["src"]

            def _parse_count(label_text: str) -> Optional[int]:
                """Find a stat counter adjacent to a label string."""
                try:
                    tags_found = soup.find_all("span", class_=re.compile(r"Counter|counter"))
                    for span in tags_found:
                        parent_text = span.parent.get_text(strip=True).lower()
                        if label_text.lower() in parent_text:
                            raw = span.get_text(strip=True).replace(",", "")
                            # Handle abbreviated numbers like "1.2k"
                            if raw.endswith("k"):
                                return int(float(raw[:-1]) * 1000)
                            return int(raw)
                except Exception:
                    pass
                return None

            public_repos = _parse_count("repositories") or _parse_count("repos")
            followers = _parse_count("followers")
            following = _parse_count("following")

        elif resp.status_code == 404:
            profile_found = False
        else:
            logger.warning("Identity: HTTP %s for %s", resp.status_code, target_url)

    except httpx.TimeoutException:
        logger.warning("Identity: timeout scraping %s", target_url)
    except Exception as exc:
        logger.error("Identity: scrape error for %s — %s", username, exc)

    # ── Playwright skeleton (JavaScript-heavy targets) ─────────────────────────
    # Uncomment and adapt for platforms requiring browser execution (LinkedIn, X, etc.)
    #
    # from playwright.async_api import async_playwright
    # async with async_playwright() as pw:
    #     browser = await pw.chromium.launch(headless=True)
    #     page = await browser.new_page()
    #     await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 ..."})
    #     await page.goto(target_url, wait_until="networkidle", timeout=15000)
    #     # Extract data with page.query_selector / page.evaluate
    #     display_name = await page.eval_on_selector("span.p-name", "el => el.innerText")
    #     await browser.close()
    # ──────────────────────────────────────────────────────────────────────────

    result = IdentityTrackingResponse(
        scan_id=scan_id,
        username=username,
        platform="GitHub",
        profile_url=target_url,
        display_name=display_name,
        bio=bio,
        public_repos=public_repos,
        followers=followers,
        following=following,
        avatar_url=avatar_url,
        profile_found=profile_found,
        logged_at=logged_at,
    )

    await _log_to_db(
        module="identity",
        target=username,
        scan_id=scan_id,
        result=result.model_dump(),
        user_uid=user_uid,
    )

    return result


# ──────────────────────────────────────────────
# §11 CHATBOT MODULE — TELEGRAM WEBHOOK
# ──────────────────────────────────────────────

async def _telegram_echo_reply(chat_id: int, text: str) -> None:
    """
    Background task: echo the message back to the Telegram chat via Bot API.

    This runs **after** the 200 OK has been returned to Telegram's servers,
    satisfying their 5-second response window requirement.

    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": f"🔍 IntrusionX SE received: {text}",
        "parse_mode": "HTML",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url, 
                json=payload,
                headers={"User-Agent": USER_AGENT}
            )
            resp.raise_for_status()
        logger.info("Telegram: echoed message to chat_id=%s", chat_id)
    except httpx.TimeoutException:
        logger.warning("Telegram: timeout sending reply to chat_id=%s", chat_id)
    except Exception as exc:
        logger.error("Telegram: echo failed for chat_id=%s — %s", chat_id, exc)


@app.post(
    "/api/v1/webhook/telegram",
    response_model=TelegramWebhookAck,
    tags=["Chatbot Webhooks — Telegram"],
    summary="Receive Telegram bot updates",
    response_description="Always returns 200 OK immediately; processing is offloaded to a background task.",
    status_code=status.HTTP_200_OK,
)
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> TelegramWebhookAck:
    """
    ## Telegram Bot Webhook Handler

    Receives Telegram `Update` objects sent by the Telegram Bot API.

    **Critical requirement:** Telegram's servers require a `200 OK` response
    within **5 seconds**. This handler immediately returns `200` and offloads
    all processing to FastAPI `BackgroundTasks`.

    ### Behaviour
    1. Parse the `chat.id` and `message.text` from the update payload.
    2. Immediately return `{"status": "accepted"}`.
    3. In the background, send an echo reply via the Telegram Bot API.

    ### Setup
    Register this URL with Telegram:
    ```
    POST https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://yourserver.com/api/v1/webhook/telegram
    ```
    """
    try:
        body = await request.json()
    except Exception:
        # Malformed JSON — still return 200 to avoid Telegram retry storm
        logger.warning("Telegram webhook: malformed JSON body received.")
        return TelegramWebhookAck(status="accepted", message="Payload parse error — ignored.")

    try:
        message = body.get("message") or body.get("edited_message", {})
        chat_id: int = message.get("chat", {}).get("id", 0)
        
        # Support uploads and missing captions
        if message.get("text"):
            text = message["text"]
        elif message.get("caption"):
            text = message["caption"]
        elif message.get("document"):
            doc_name = message["document"].get("file_name", "a document")
            text = f"[DOCUMENT RECEIVED] {doc_name}"
        elif message.get("photo"):
            text = "[PHOTO RECEIVED]"
        elif message.get("video"):
            text = "[VIDEO RECEIVED]"
        elif message.get("audio") or message.get("voice"):
            text = "[AUDIO RECEIVED]"
        else:
            text = "[MEDIA/DATA RECEIVED]"

        logger.info("Telegram: update from chat_id=%s text='%s'", chat_id, text[:80])

        if chat_id:
            background_tasks.add_task(_telegram_echo_reply, chat_id, text)
    except Exception as exc:
        logger.error("Telegram webhook: dispatch error — %s", exc)

    return TelegramWebhookAck(
        status="accepted",
        message="Update received and queued for processing.",
    )


# ──────────────────────────────────────────────
# §12 CHATBOT MODULE — WHATSAPP WEBHOOK
# ──────────────────────────────────────────────

@app.get(
    "/api/v1/webhook/whatsapp",
    response_model=None,
    tags=["Chatbot Webhooks — WhatsApp"],
    summary="Meta hub.challenge verification endpoint",
    response_description="Returns the hub.challenge value as plain text to verify the webhook with Meta.",
    status_code=status.HTTP_200_OK,
)
async def whatsapp_verify(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
) -> Any:
    """
    ## WhatsApp Webhook — Meta Hub Challenge Verification

    Meta sends a `GET` request to this endpoint to verify your webhook URL
    during initial registration in the Meta for Developers console.

    ### Verification flow
    1. Meta sends: `?hub.mode=subscribe&hub.verify_token=<YOUR_TOKEN>&hub.challenge=<CHALLENGE>`
    2. This handler validates the verify token against `WHATSAPP_VERIFY_TOKEN`.
    3. Returns the `hub.challenge` value as a plain-text `200 OK` response.

    ### Configuration
    Set the `WHATSAPP_VERIFY_TOKEN` environment variable to a strong random string
    and configure the same value in the Meta Developer Portal.
    """
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        logger.info("WhatsApp: hub challenge verified successfully.")
        # Return plain integer challenge as required by Meta
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=hub_challenge, status_code=200)

    logger.warning(
        "WhatsApp: hub challenge FAILED — mode=%s token_match=%s",
        hub_mode,
        hub_verify_token == WHATSAPP_VERIFY_TOKEN,
    )
    raise HTTPException(status_code=403, detail="Webhook verification failed.")


async def _process_whatsapp_message(payload: Dict[str, Any]) -> None:
    """
    Background task: process an inbound WhatsApp Cloud API message.

    Parses the message and sends an acknowledgement reply via the WhatsApp
    Cloud API. Extend this function to route messages to your OSINT engine.

    """
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return

        msg = messages[0]
        from_number: str = msg.get("from", "")
        msg_type: str = msg.get("type", "text")
        body: str = msg.get("text", {}).get("body", "") if msg_type == "text" else f"[{msg_type}]"

        logger.info("WhatsApp: message from=%s body='%s'", from_number, body[:80])

        # Send acknowledgement reply
        if from_number:
            reply_url = (
                f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_NUMBER_ID}/messages"
            )
            reply_payload = {
                "messaging_product": "whatsapp",
                "to": from_number,
                "type": "text",
                "text": {"body": f"✅ IntrusionX SE received your message: {body}"},
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    reply_url,
                    json=reply_payload,
                    headers={
                        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
                        "User-Agent": USER_AGENT
                    },
                )
                resp.raise_for_status()
    except Exception as exc:
        logger.error("WhatsApp background processor error: %s", exc)


@app.post(
    "/api/v1/webhook/whatsapp",
    response_model=TelegramWebhookAck,
    tags=["Chatbot Webhooks — WhatsApp"],
    summary="Receive inbound WhatsApp Cloud API messages",
    response_description="Always returns 200 OK immediately; message processing runs in background.",
    status_code=status.HTTP_200_OK,
)
async def whatsapp_inbound(
    request: Request,
    background_tasks: BackgroundTasks,
) -> TelegramWebhookAck:
    """
    ## WhatsApp Webhook — Inbound Message Handler

    Receives inbound message notifications from the **WhatsApp Cloud API**.

    **Critical:** Meta requires a `200 OK` response within **20 seconds**.
    This handler returns immediately and delegates processing to a background task.

    ### Supported message types
    - `text` — Plain text messages
    - `image`, `audio`, `video`, `document` — Media type identified and logged
    - `interactive` — Button/list responses

    ### Payload structure (Meta Cloud API v19.0)
    ```json
    {
      "object": "whatsapp_business_account",
      "entry": [{ "changes": [{ "value": { "messages": [{...}] } }] }]
    }
    ```
    """
    try:
        body = await request.json()
    except Exception:
        logger.warning("WhatsApp inbound: malformed JSON.")
        return TelegramWebhookAck(status="accepted", message="Payload ignored.")

    try:
        # Validate this is a WhatsApp notification
        if body.get("object") == "whatsapp_business_account":
            background_tasks.add_task(_process_whatsapp_message, body)
    except Exception as exc:
        logger.error("WhatsApp inbound dispatch error: %s", exc)

    return TelegramWebhookAck(
        status="accepted",
        message="Message received and queued for processing.",
    )


# ──────────────────────────────────────────────
# §13 APPLICATION LIFECYCLE
# ──────────────────────────────────────────────

@app.on_event("startup")
async def on_startup() -> None:
    """
    Application startup sequence.
    Initialises Firebase, PostgreSQL, and S3 leak hunting database in dependency order.
    Server starts even if either service is unreachable.
    """
    logger.info("=" * 60)
    logger.info("  %s  v%s  —  Starting up", APP_NAME, APP_VERSION)
    logger.info("=" * 60)
    _init_firebase()
    await _init_db()
    
    # Initialize S3 leak hunting database pool
    try:
        await initialize_pool()
        logger.info("S3 leak hunting database pool initialized.")
    except Exception as e:
        logger.error("S3 leak hunting database initialization FAILED: %s", e)
        # Server continues; S3 endpoints will return 503 if DB is unavailable
    
    logger.info("Startup complete. API is ready to serve requests.")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """
    Graceful shutdown: close both PostgreSQL connection pools (main & S3 hunting).
    """
    global _db_pool
    if _db_pool is not None:
        await _db_pool.close()
        logger.info("PostgreSQL connection pool closed.")
    
    # Close S3 leak hunting database pool
    try:
        await close_pool()
    except Exception as e:
        logger.error("Error closing S3 hunting pool: %s", e)
    
    logger.info("%s shutdown complete.", APP_NAME)


# ──────────────────────────────────────────────
# HEALTH CHECK
# ──────────────────────────────────────────────

@app.get(
    "/",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Service health check",
    include_in_schema=True,
)
async def health_check() -> HealthResponse:
    """Returns service health status. Suitable for load-balancer probes."""
    return HealthResponse(
        status="healthy",
        service=APP_NAME,
        version=APP_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Detailed health check with dependency status",
)
async def detailed_health() -> HealthResponse:
    """
    Extended health endpoint that reveals database and Firebase connectivity.
    Use this for internal monitoring (Prometheus, Grafana, Datadog).
    """
    db_status = "connected" if _db_pool is not None else "unavailable"
    firebase_status = "connected" if _firebase_app is not None else "unavailable"
    overall = "healthy" if _db_pool is not None and _firebase_app is not None else "degraded"

    return HealthResponse(
        status=f"{overall} | db={db_status} | firebase={firebase_status}",
        service=APP_NAME,
        version=APP_VERSION,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ──────────────────────────────────────────────
# §14 S3 LEAK HUNTING ENDPOINTS
# ──────────────────────────────────────────────

@app.post(
    "/api/v1/scan/leaks",
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
    ## Start S3 Bucket Leak Scan
    
    Initiates an asynchronous scan for exposed or misconfigured Amazon S3 buckets
    associated with the target domain.
    
    ### Returns immediately (202 Accepted)
    - A `task_id` UUID for tracking the scan status
    - Poll the `/api/v1/scan/{task_id}` endpoint to get results
    
    ### How it works
    1. Extracts the domain base name (e.g., "example" from "example.com")
    2. Generates 50+ common S3 bucket name permutations
    3. Concurrently probes each bucket for public access
    4. Stores results in PostgreSQL for later retrieval
    
    ### Response codes
    - **200 OK** → Bucket is **publicly accessible** (VULNERABLE)
    - **403 Forbidden** → Bucket exists but is **protected** (SECURE)
    - **404 Not Found** → Bucket doesn't exist (ignored)
    - **Timeout** → Network issue or AWS rate-limiting (ignored)
    
    ### Example
    ```bash
    curl -X POST http://localhost:8000/api/v1/scan/leaks \
      -H "Content-Type: application/json" \
      -d '{"domain": "example.com"}'
    
    # Response:
    # {
    #   "task_id": "a1b2c3d4-e5f6-4789-0abc-def123456789",
    #   "message": "Scan started",
    #   "estimated_duration_seconds": 60
    # }
    
    # Poll for results:
    curl http://localhost:8000/api/v1/scan/a1b2c3d4-e5f6-4789-0abc-def123456789
    ```
    """
    task_id = uuid.uuid4()
    
    logger.info(
        "S3 leak scan initiated: task_id=%s domain=%s user=%s",
        task_id,
        request.domain,
        user.get("email") if user else "anonymous"
    )
    
    # Trigger background worker
    background_tasks.add_task(run_leak_scan, task_id, request.domain)
    
    return S3ScanInitResponse(
        task_id=str(task_id),
        message="Scan started. Check status at /api/v1/scan/{task_id}",
        estimated_duration_seconds=60
    )


@app.get(
    "/api/v1/scan/{task_id}",
    response_model=S3ScanStatusResponse,
    tags=["S3 Leak Hunting"],
    summary="Poll S3 leak scan status",
)
async def get_s3_leak_scan_status(
    task_id: str,
    user: Optional[Dict[str, Any]] = Depends(optional_auth),
) -> S3ScanStatusResponse:
    """
    ## Get S3 Leak Scan Status
    
    Polls the status and results of a previously initiated S3 leak scan.
    
    ### Status lifecycle
    1. **"running"** — Scan is in progress; results will be empty
    2. **"completed"** — Scan finished; results contain buckets found
    3. **"failed"** — Scan encountered an error; see error field
    
    ### Results structure (when status='completed')
    ```json
    {
      "domain": "example.com",
      "base_name": "example",
      "total_checked": 52,
      "buckets_found": {
        "open": [
          {"bucket_name": "example-dev", "http_code": 200},
          {"bucket_name": "example-backup", "http_code": 200}
        ],
        "closed": [
          {"bucket_name": "example-prod", "http_code": 403}
        ]
      },
      "errors": {
        "timeout": ["backup-example"],
        "connection_failed": []
      }
    }
    ```
    
    ### Polling strategy
    ```python
    import time
    from uuid import UUID
    import httpx
    
    task_id = "a1b2c3d4-e5f6-4789-0abc-def123456789"
    max_attempts = 360  # 30 minutes with 5-second polls
    
    for attempt in range(max_attempts):
        response = httpx.get(f"http://localhost:8000/api/v1/scan/{task_id}")
        scan = response.json()
        
        if scan["status"] == "running":
            print(f"Scan in progress... ({attempt+1}/{max_attempts})")
            time.sleep(5)  # Poll every 5 seconds
        else:
            print(f"Scan complete: {scan['status']}")
            if scan['results']:
                print(f"Found {len(scan['results']['buckets_found']['open'])} open buckets")
            break
    ```
    """
    try:
        # Parse task_id as UUID
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid task_id format (expected UUID): {task_id}"
        )
    
    # Query PostgreSQL for scan record
    try:
        scan_record = await get_scan(task_uuid)
    except Exception as e:
        logger.error("Failed to query scan status: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is currently unavailable. Please try again later."
        )
    
    if scan_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scan task not found: {task_id}"
        )
    
    # Build response
    status_val = scan_record["status"]
    results = None
    error = None
    
    if status_val == "completed":
        # Parse JSONB results
        import json
        results_json = scan_record["results"] or {}
        if isinstance(results_json, str):
            results_json = json.loads(results_json)
        results = S3ScanResults(**results_json)
    elif status_val == "failed":
        # Extract error message
        results_json = scan_record["results"] or {}
        if isinstance(results_json, str):
            import json
            results_json = json.loads(results_json)
        error = results_json.get("error", "Unknown error")
    
    return S3ScanStatusResponse(
        task_id=str(task_uuid),
        target_domain=scan_record["target_domain"],
        status=status_val,
        results=results,
        error=error
    )


# ──────────────────────────────────────────────
# §15 ENTRYPOINT
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,          # Set to False in production
        log_level="info",
        access_log=True,
    )
