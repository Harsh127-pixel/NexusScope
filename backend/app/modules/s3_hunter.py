"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    NexusScope — S3 Bucket Leak Hunter                       ║
║              Scans for exposed & misconfigured Amazon S3 buckets            ║
╚══════════════════════════════════════════════════════════════════════════════╝

FUNCTIONALITY
─────────────
 ✓  Extract base domain name from input URLs
 ✓  Generate 50+ common S3 bucket name permutations
 ✓  Async HTTP scanning of S3 endpoints
 ✓  Graceful error handling (timeouts, DNS failures, etc.)
 ✓  Classify buckets by HTTP response (Open/Vulnerable, Closed/Secure, Not Found)
 ✓  Return structured findings

THREAT LANDSCAPE
────────────────
Exposed S3 buckets are a critical threat vector. Common misconfiguration patterns:
  • Public read ACL (anyone can list & download objects)
  • VCP:* statements in bucket policies (world-accessible)
  • Disabled block-public-access settings
  • Missing encryption
  • Deleted bucket (allows name-jacking)

Response codes:
  ✓ 200 OK         → Bucket exists & is accessible (VULNERABLE)
  ✗ 403 Forbidden  → Bucket exists but is locked (SECURE)
  ✗ 404 Not Found  → Bucket doesn't exist (ignore)
  ⚠ Timeout/Error  → Log & continue (network issues, rate-limiting by AWS)

BUCKET NAME GENERATION
──────────────────────
For domain "example.com", we generate permutations like:
  - example-dev, example-prod, example-backup, example-staging
  - backup-example, dev-example, prod-example
  - example-aws, example-s3, example-cdn, example-logs
  - example123, example-assets, example-database
  - exampleapi, example-api, example-config
  ...and 30+ more variants

USAGE
─────
    import asyncio
    from backend.app.modules.s3_hunter import hunt_s3_buckets
    
    results = await hunt_s3_buckets("example.com")
    print(results)
    # Output: {
    #     "total_checked": 52,
    #     "open_buckets": [
    #         {"name": "example-dev", "status": "open"},
    #         {"name": "example-backup", "status": "open"}
    #     ],
    #     "closed_buckets": [
    #         {"name": "example-prod", "status": "closed"}
    #     ],
    #     "errors": []
    # }
"""

import asyncio
import logging
import re
from typing import Dict, List, Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("s3_hunter")

# ─────────────────────────────────────────────
#  §1  BUCKET NAME GENERATION
#  ─────────────────────────────────────────────
def _extract_domain_basename(domain: str) -> str:
    """
    Extracts the base name from a domain URL.
    
    Examples:
        "https://www.example.com" → "example"
        "example.com" → "example"
        "https://dev.example.co.uk" → "example"
        "my-company.io" → "my-company"
    
    PARAMS:
        domain: Full URL or domain name
    
    RETURNS:
        Base domain name (without TLD, without www)
    """
    # Parse URL if provided with scheme
    if "://" in domain:
        parsed = urlparse(domain)
        domain = parsed.hostname or domain
    
    # Clean up trailing slashes
    domain = domain.strip().lower().rstrip("/")
    
    # Remove www prefix
    if domain.startswith("www."):
        domain = domain[4:]
    
    # Split by dot and take the first label (base name)
    # For "example.co.uk", this gives "example"
    # For "my-company.io", this gives "my-company"
    parts = domain.split(".")
    if parts:
        return parts[0]
    
    return domain


def _generate_bucket_permutations(base_name: str) -> List[str]:
    """
    Generates 50+ common S3 bucket name permutations from a base domain.
    
    These permutations cover:
      • Development/staging environments (dev, staging, prod, uat)
      • Backup patterns (backup, backups, archive)
      • Service identifiers (api, cdn, logs, assets, database)
      • Environment prefixes and suffixes
      • Common typos and variations
    
    PARAMS:
        base_name: Base domain name (e.g., "example")
    
    RETURNS:
        List of 50+ bucket name candidates to probe
    
    NOTE:
        S3 bucket names must be:
          • 3-63 characters (lowercase only)
          • Start and end with alphanumeric
          • May contain hyphens (not at edges)
        We filter invalid names here.
    """
    permutations = []
    
    # ── Environment variants ────────────────────────
    env_prefixes = ["", "dev-", "prod-", "staging-", "test-", "uat-"]
    env_suffixes = ["", "-dev", "-prod", "-staging", "-test", "-uat"]
    
    for prefix in env_prefixes:
        for suffix in env_suffixes:
            candidate = f"{prefix}{base_name}{suffix}"
            if 3 <= len(candidate) <= 63:
                permutations.append(candidate.lower().replace("--", "-"))
    
    # ── Backup & Archive patterns ───────────────────
    backup_patterns = [
        f"backup-{base_name}",
        f"{base_name}-backup",
        f"backups-{base_name}",
        f"{base_name}-backups",
        f"archive-{base_name}",
        f"{base_name}-archive",
        f"data-{base_name}",
        f"{base_name}-data",
    ]
    permutations.extend(backup_patterns)
    
    # ── Service identifiers ─────────────────────────
    services = ["api", "cdn", "logs", "assets", "database", "config", "secrets", "media"]
    for service in services:
        permutations.extend([
            f"{base_name}-{service}",
            f"{service}-{base_name}",
        ])
    
    # ── AWS-specific patterns ───────────────────────
    aws_patterns = [
        f"{base_name}-aws",
        f"{base_name}-s3",
        f"{base_name}-storage",
        f"s3-{base_name}",
    ]
    permutations.extend(aws_patterns)
    
    # ── Numeric & variation patterns ────────────────
    variations = [
        f"{base_name}123",
        f"{base_name}456",
        f"{base_name}-01",
        f"{base_name}-2024",
        f"{base_name}prod",
        f"{base_name}dev",
        f"prod{base_name}",
        f"dev{base_name}",
    ]
    permutations.extend(variations)
    
    # ── Remove duplicates and invalid names ─────────
    valid_buckets = set()
    for bucket in permutations:
        # S3 bucket naming rules: 3-63 chars, lowercase, alphanumeric + hyphens
        # Hyphens can't be at start/end
        bucket_clean = bucket.lower().strip()
        
        if (3 <= len(bucket_clean) <= 63 and
            bucket_clean[0].isalnum() and
            bucket_clean[-1].isalnum() and
            re.match(r"^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$|^[a-z0-9]$", bucket_clean)):
            valid_buckets.add(bucket_clean)
    
    return sorted(list(valid_buckets))


# ─────────────────────────────────────────────
#  §2  S3 SCANNING ENGINE
#  ─────────────────────────────────────────────
async def _check_bucket_access(
    client: httpx.AsyncClient,
    bucket_name: str,
    timeout: int = 5
) -> Dict[str, Any]:
    """
    Checks if an S3 bucket is publicly accessible via HEAD request.
    
    AWS S3 endpoints:
      • Standard: https://bucket-name.s3.amazonaws.com
      • Regional: https://bucket-name.s3.region.amazonaws.com
      • Legacy (virtual-hosted): https://bucket-name.s3-region.amazonaws.com
    
    We probe the standard endpoint first. Response codes:
      • 200 OK → Bucket is accessible (possible data exposure)
      • 403 Forbidden → Bucket is protected by ACL or policy
      • 404 Not Found → Bucket doesn't exist (don't report)
      • 5xx or timeout → Assume not found (AWS throttling/rate-limit)
    
    PARAMS:
        client: Shared AsyncClient for connection pooling
        bucket_name: Name of bucket to probe
        timeout: HTTP request timeout (default 5 seconds)
    
    RETURNS:
        {
            "bucket_name": "example-dev",
            "status": "open" | "closed" | "not_found" | "error",
            "http_code": 200 | 403 | 404 | 0,
            "error": None | "timeout" | "dns_failed" | "connection_reset"
        }
    """
    url = f"https://{bucket_name}.s3.amazonaws.com"
    
    try:
        # Use HEAD request (faster, no body returned)
        response = await client.head(
            url,
            follow_redirects=False,
            timeout=timeout
        )
        
        http_code = response.status_code
        
        if http_code == 200:
            return {
                "bucket_name": bucket_name,
                "status": "open",
                "http_code": 200,
                "error": None
            }
        elif http_code == 403:
            return {
                "bucket_name": bucket_name,
                "status": "closed",
                "http_code": 403,
                "error": None
            }
        elif http_code == 404:
            # Bucket doesn't exist; don't report
            return {
                "bucket_name": bucket_name,
                "status": "not_found",
                "http_code": 404,
                "error": None
            }
        else:
            # Unusual response (5xx, etc.)
            return {
                "bucket_name": bucket_name,
                "status": "not_found",
                "http_code": http_code,
                "error": f"http_{http_code}"
            }
    
    except asyncio.TimeoutError:
        logger.debug(f"Timeout probing {bucket_name}")
        return {
            "bucket_name": bucket_name,
            "status": "error",
            "http_code": 0,
            "error": "timeout"
        }
    
    except httpx.ConnectError as e:
        # DNS resolution failed or connection refused
        logger.debug(f"Connect error for {bucket_name}: {type(e).__name__}")
        return {
            "bucket_name": bucket_name,
            "status": "error",
            "http_code": 0,
            "error": "connection_failed"
        }
    
    except httpx.RequestError as e:
        # Generic HTTP error (SSL, DNS, network)
        logger.debug(f"Request error for {bucket_name}: {type(e).__name__}")
        return {
            "bucket_name": bucket_name,
            "status": "error",
            "http_code": 0,
            "error": str(type(e).__name__).lower()
        }
    
    except Exception as e:
        logger.error(f"Unexpected error probing {bucket_name}: {e}")
        return {
            "bucket_name": bucket_name,
            "status": "error",
            "http_code": 0,
            "error": "unknown"
        }


async def hunt_s3_buckets(domain: str) -> Dict[str, Any]:
    """
    Main S3 bucket hunting function. Scans for exposed buckets associated with a domain.
    
    WORKFLOW:
      1. Extract base domain name from input (handles URLs with www, paths, etc.)
      2. Generate 50+ bucket name permutations
      3. Create shared AsyncClient with connection pooling (5 concurrent connections)
      4. Probe all buckets asynchronously
      5. Aggregate results by status (open, closed, errors)
      6. Return structured findings
    
    PARAMS:
        domain: Target domain or URL
                Examples: "example.com", "https://www.example.com", "my-company.io"
    
    RETURNS:
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
    
    PERFORMANCE:
        With ~50 buckets and timeout=5s:
          • Sequential: ~250 seconds (too slow)
          • Parallel (5 concurrent): ~50 seconds
          • Parallel (10 concurrent): ~30 seconds
        We use semaphore with limit=10 for optimal throughput.
    
    USAGE:
        results = await hunt_s3_buckets("example.com")
        print(f"Found {len(results['buckets_found']['open'])} open buckets")
    """
    base_name = _extract_domain_basename(domain)
    bucket_candidates = _generate_bucket_permutations(base_name)
    
    logger.info(f"Starting S3 hunt for domain={domain} (base={base_name})")
    logger.info(f"Generated {len(bucket_candidates)} bucket candidates to probe")
    
    # Collect results
    open_buckets = []
    closed_buckets = []
    errors_by_type = {}
    
    # Create AsyncClient with connection pooling
    limits = httpx.Limits(
        max_connections=10,
        max_keepalive_connections=5,
        keepalive_expiry=30
    )
    
    async with httpx.AsyncClient(limits=limits, timeout=5.0) as client:
        # Create semaphore to limit concurrent probes
        semaphore = asyncio.Semaphore(10)
        
        async def check_with_semaphore(bucket: str):
            """Wrapper to respect semaphore limit"""
            async with semaphore:
                return await _check_bucket_access(client, bucket)
        
        # Probe all buckets concurrently
        tasks = [check_with_semaphore(bucket) for bucket in bucket_candidates]
        results = await asyncio.gather(*tasks, return_exceptions=False)
    
    # Aggregate results
    for result in results:
        if result.get("status") == "open":
            open_buckets.append({
                "bucket_name": result["bucket_name"],
                "http_code": result["http_code"]
            })
            logger.warning(
                f"🔓 OPEN BUCKET FOUND: {result['bucket_name']} "
                f"(HTTP {result['http_code']})"
            )
        
        elif result.get("status") == "closed":
            closed_buckets.append({
                "bucket_name": result["bucket_name"],
                "http_code": result["http_code"]
            })
        
        elif result.get("status") == "error" and result.get("error"):
            error_type = result["error"]
            if error_type not in errors_by_type:
                errors_by_type[error_type] = []
            errors_by_type[error_type].append(result["bucket_name"])
    
    return {
        "domain": domain,
        "base_name": base_name,
        "total_checked": len(bucket_candidates),
        "buckets_found": {
            "open": open_buckets,
            "closed": closed_buckets
        },
        "errors": errors_by_type if errors_by_type else {}
    }
