# S3 Leak Hunting Module — Setup & Usage Guide

## Overview

The **S3 Leak Hunting Module** is an end-to-end system for scanning target domains for publicly exposed and misconfigured Amazon S3 buckets. This represents a critical security issue, as exposed buckets can leak sensitive data, customer information, configurations, and secrets.

---

## Architecture

### The four-component system:

```
┌─────────────────────────────────────────────────────────────────┐
│                          FastAPI (main.py)                      │
│  POST /api/v1/scan/leaks  →  GET /api/v1/scan/{task_id}        │
└────────┬────────────────────────────────────────────────────────┘
         │ BackgroundTasks
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Background Worker (workers.py)              │
│    run_leak_scan(task_id, domain) - Orchestrates scan lifecycle │
└────────┬───────────────────────────┬────────────────────────────┘
         │                           │
         │ INSERT/UPDATE             │ Awaits
         ▼                           ▼
    PostgreSQL          ┌──────────────────────────────┐
    (database.py)       │   S3 Hunter (s3_hunter.py)   │
    scans table         │  • Generate bucket names     │
                        │  • Probe S3 endpoints        │
                        │  • Classify findings         │
                        └──────────────────────────────┘
```

### Files

| File | Purpose |
|------|---------|
| `backend/database.py` | PostgreSQL connection pool & schema migrations |
| `backend/app/modules/s3_hunter.py` | S3 bucket name generation & HTTP probing |
| `backend/workers.py` | Background task orchestration & DB updates |
| `backend/main.py` | FastAPI routes + startup/shutdown events |

---

## Environment Setup

### 1. PostgreSQL Database

You must have a PostgreSQL database. The module uses **Neon** (serverless PostgreSQL service) by default.

#### Option A: Use Neon (Recommended for serverless)

1. Go to [https://neon.tech](https://neon.tech) and create a free account
2. Create a new project
3. Copy your connection string (looks like):
   ```
   postgresql://username:password@ep-XXXXX-pooler.REGION.aws.neon.tech/neondb?sslmode=require
   ```
4. Set the `DATABASE_URL` in `backend/.env`

#### Option B: Use local PostgreSQL

```bash
# Install PostgreSQL (macOS)
brew install postgresql@15

# Start the server
brew services start postgresql@15

# Create a database
createdb nexusscope_s3

# Set DATABASE_URL in .env
DATABASE_URL=postgresql://localhost:5432/nexusscope_s3
```

#### Option C: Use Docker

```bash
docker run --name postgres-neondb \
  -e POSTGRES_DB=neondb \
  -e POSTGRES_PASSWORD=password \
  -p 5432:5432 \
  -d postgres:15

# Set DATABASE_URL in .env
DATABASE_URL=postgresql://postgres:password@localhost:5432/neondb
```

### 2. Environment Variables (.env)

Required in `backend/.env`:

```bash
# PostgreSQL Connection — REQUIRED
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DB?sslmode=require

# API Server (optional)
API_HOST=127.0.0.1
API_PORT=8000

# Firebase (optional but recommended for auth)
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_CRED_PATH=./shared/firebase-service-account.json
```

### 3. Dependencies

Already included in `backend/requirements.txt`:
- `asyncpg` — PostgreSQL async client
- `httpx` — Async HTTP client
- `fastapi` — Web framework
- `pydantic` — Data validation

No additional packages needed.

---

## Running the Module

### Step 1: Start the backend server

```bash
cd backend
python -m pip install -r requirements.txt
export DATABASE_URL="postgresql://USER:PASSWORD@HOST/DB"
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Step 2: Test the API

#### Start a scan:

```bash
curl -X POST http://localhost:8000/api/v1/scan/leaks \
  -H "Content-Type: application/json" \
  -d '{"domain": "example.com"}'
```

**Response:**
```json
{
  "task_id": "a1b2c3d4-e5f6-4789-0abc-def123456789",
  "message": "Scan started. Check status at /api/v1/scan/{task_id}",
  "estimated_duration_seconds": 60
}
```

#### Poll for results:

```bash
curl http://localhost:8000/api/v1/scan/a1b2c3d4-e5f6-4789-0abc-def123456789
```

**Response while running:**
```json
{
  "task_id": "a1b2c3d4-e5f6-4789-0abc-def123456789",
  "target_domain": "example.com",
  "status": "running",
  "results": null,
  "error": null
}
```

**Response when complete:**
```json
{
  "task_id": "a1b2c3d4-e5f6-4789-0abc-def123456789",
  "target_domain": "example.com",
  "status": "completed",
  "results": {
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
      "timeout": ["some-bucket"],
      "connection_failed": []
    }
  },
  "error": null
}
```

---

## Detailed Configuration

### Database Initialization

When `initialize_pool()` is called in `main.py` startup, the module:

1. **Creates connection pool** with optimal settings:
   - Min: 5 connections
   - Max: 20 connections
   - Command timeout: 10 seconds
   - Connection timeout: 30 seconds
   - SSL required for Neon

2. **Runs schema migration** via `_create_schema()`:
   - Creates `scans` table if it doesn't exist
   - Creates indices on `status` and `created_at` for fast queries
   - All operations are idempotent (safe to run multiple times)

### Bucket Name Generation

The `hunt_s3_buckets()` function generates permutations from domain "example.com":

**Patterns generated (50+ variants):**
- Environment variants: `dev-`, `prod-`, `staging-`, `test-`, `uat-`
- Suffixes: `-dev`, `-prod`, `-staging`, `-backup`, `-archive`
- Services: `-api`, `-cdn`, `-logs`, `-assets`, `-database`, `-config`
- AWS-specific: `-aws`, `-s3`, `-storage`
- Numeric: `example123`, `example-2024`, `prod-example`

**Example permutations for "example.com":**
```
example-dev          dev-example          example-prod
example-backup       backup-example       example-staging
example-api          api-example          example-cdn
example-logs         logs-example         example-assets
example-database     example-aws          example-s3
example-config       example-secrets      example-media
...and 35+ more
```

### S3 Probing Logic

For each bucket candidate, the system:

1. **Sends HTTP HEAD request** to `https://BUCKET.s3.amazonaws.com`
2. **Interprets response:**
   - `200 OK` → Bucket is **open/vulnerable** (publicly accessible)
   - `403 Forbidden` → Bucket is **closed/secure** (protected by ACL)
   - `404 Not Found` → Bucket doesn't exist (ignored)
   - `Timeout` → Network issue; AWS rate-limiting; skip quietly
3. **Aggregates results** by status

### Concurrency & Performance

- **Default concurrency:** 10 concurrent probes (configurable via semaphore)
- **Timeout per probe:** 5 seconds
- **Total probes:** ~50 buckets
- **Estimated duration:** 30-60 seconds

**Tuning:**

In `s3_hunter.py`, adjust the semaphore limit:

```python
semaphore = asyncio.Semaphore(10)  # ← Change this number
```

Higher = faster but more load; lower = slower but fewer connections.

---

## Database Schema

### `scans` table

```sql
CREATE TABLE scans (
    id UUID PRIMARY KEY,                      -- Scan task UUID
    target_domain TEXT NOT NULL,              -- Domain being scanned
    status TEXT NOT NULL                      -- 'running', 'completed', 'failed'
      CHECK (status IN ('running', 'completed', 'failed')),
    results JSONB DEFAULT '{}'::jsonb,        -- Scan findings (JSON format)
    created_at TIMESTAMPTZ DEFAULT NOW(),     -- Scan start time
    updated_at TIMESTAMPTZ DEFAULT NOW()      -- Last update time
);

-- Indices for fast queries
CREATE INDEX idx_scans_status ON scans(status);
CREATE INDEX idx_scans_created_at ON scans(created_at DESC);
```

### Sample row after completion

```sql
SELECT * FROM scans WHERE id = '550e8400-e29b-41d4-a716-446655440000';

id                                   | target_domain | status    | results | created_at | updated_at
─────────────────────────────────────┼───────────────┼───────────┼──────────────┼────────────┼────────────
550e8400-e29b-41d4-a716-446655440000 | example.com   | completed | {...}   | 2026-04-11 | 2026-04-11
```

Where `results` is:

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
    "timeout": ["some-bucket"],
    "connection_failed": []
  }
}
```

---

## Error Handling

### Graceful timeout handling

```python
try:
    response = await client.head(url, timeout=5)
except asyncio.TimeoutError:
    # Logged but doesn't block other probes
    return {"status": "error", "error": "timeout"}
except httpx.ConnectError:
    # DNS resolution failed or connection refused
    return {"status": "error", "error": "connection_failed"}
```

### Database connection fallback

If the PostgreSQL connection fails:

1. API returns `503 Service Unavailable`
2. Worker writes error to disk (optional; can be added)
3. Logs contain full error traceback
4. Server continues serving other requests

---

## Logging & Debugging

### Enable verbose logging

In `main.py`:

```python
logging.basicConfig(
    level=logging.DEBUG,  # ← Change to DEBUG
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
```

### Example log output

```
2026-04-11T14:22:45 | INFO     | workers              | Starting S3 leak scan task_id=550e8400-e29b-41d4 domain=example.com
2026-04-11T14:22:45 | INFO     | database             | ✓ Inserted scan record: 550e8400-e29b-41d4 for example.com
2026-04-11T14:22:45 | INFO     | s3_hunter            | Starting S3 hunt for domain=example.com (base=example)
2026-04-11T14:22:45 | INFO     | s3_hunter            | Generated 52 bucket candidates to probe
2026-04-11T14:22:47 | WARNING  | s3_hunter            | 🔓 OPEN BUCKET FOUND: example-dev (HTTP 200)
2026-04-11T14:22:48 | WARNING  | s3_hunter            | 🔓 OPEN BUCKET FOUND: example-backup (HTTP 200)
2026-04-11T14:23:15 | INFO     | s3_hunter            | S3 hunt completed: 2 open buckets found
2026-04-11T14:23:15 | INFO     | database             | ✓ Updated scan 550e8400-e29b-41d4 with status=completed
2026-04-11T14:23:15 | INFO     | workers              | ✓ S3 leak scan task completed: 550e8400-e29b-41d4
```

### Query scan history

```sql
-- All scans with open buckets
SELECT id, target_domain, status, 
       (results->'buckets_found'->'open') as open_buckets
FROM scans 
WHERE results @> '{"buckets_found": {"open": []}}'::jsonb
  AND results->'buckets_found'->'open' != '[]'::jsonb;

-- All failed scans
SELECT id, target_domain, (results->>'error') as error
FROM scans 
WHERE status = 'failed';

-- Scans by domain (last 24 hours)
SELECT target_domain, COUNT(*) as scan_count
FROM scans 
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY target_domain
ORDER BY scan_count DESC;
```

---

## Production Deployment

### Docker Compose

Create `docker-compose.yml`:

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: nexusscope_s3
      POSTGRES_PASSWORD: YourSecurePassword123
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  backend:
    build: ./backend
    depends_on:
      - postgres
    environment:
      DATABASE_URL: postgresql://postgres:YourSecurePassword123@postgres:5432/nexusscope_s3
      API_HOST: 0.0.0.0
      API_PORT: 8000
    ports:
      - "8000:8000"

volumes:
  postgres_data:
```

Deploy:

```bash
docker-compose up -d
```

### Kubernetes Secrets (GKE, EKS, AKS)

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: s3-leak-hunting-db
type: Opaque
stringData:
  database-url: postgresql://user:password@neon-host/db?sslmode=require
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nexusscope-backend
spec:
  template:
    spec:
      containers:
        - name: api
          image: nexusscope:backend-latest
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: s3-leak-hunting-db
                  key: database-url
```

---

## Troubleshooting

### "Database is currently unavailable"

**Cause:** PostgreSQL connection failed.

**Fix:**
1. Check `DATABASE_URL` is set correctly
2. Verify PostgreSQL is running: `psql "postgresql://..."`
3. Check firewall rules (port 5432 must be open)
4. For Neon, ensure `sslmode=require` in URL

### "Invalid task_id format (expected UUID)"

**Cause:** You passed an invalid UUID in the URL.

**Fix:** Ensure task_id is a valid UUID:
```bash
curl http://localhost:8000/api/v1/scan/550e8400-e29b-41d4-a716-446655440000
#                                   ↑ Valid UUID format ↑
```

### Scan stuck in "running" status

**Cause:** Worker failed silently; DB not updated.

**Fix:**
1. Check logs: `grep ERROR backend.log`
2. Verify DB is writable: `psql -c "INSERT INTO scans ..."`
3. Restart FastAPI: `kill $(lsof -t -i :8000) && python -m uvicorn main:app`

### "Connection timeout" errors from s3_hunter

**Cause:** AWS is rate-limiting or your network is slow.

**Fix:**
- The system ignores timeouts by design (safe behavior)
- Increase timeout in `s3_hunter.py` line 205: `timeout=10.0`
- Reduce concurrency: `semaphore = asyncio.Semaphore(5)`

---

## Performance Benchmarks

| Config | Duration | Buckets Checked |
|--------|----------|-----------------|
| 5 concurrent, timeout=10s | 100s | 50 |
| 10 concurrent, timeout=5s | 30s | 50 |
| 20 concurrent, timeout=5s | 20s | 50 |

**Recommended:** 10 concurrent, 5s timeout = good balance of speed & reliability.

---

## Security Considerations

### 1. Rate Limiting

AWS has soft/hard limits on unauthed requests to S3:

> ~100 GET/HEAD requests per second per IP

If you hit this, add backoff:

```python
import asyncio
for bucket in buckets:
    await asyncio.sleep(0.1)  # 100ms delay between probes
    await _check_bucket_access(client, bucket)
```

### 2. Authenticated Scans

For AWS accounts you own, use IAM credentials:

```python
import aioboto3

session = aioboto3.Session(
    aws_access_key_id="AKIAIOSFODNN7EXAMPLE",
    aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
)

async with session.client("s3") as s3_client:
    response = await s3_client.get_bucket_acl(Bucket=bucket_name)
```

### 3. Data Retention Policy

It's recommended to archive/delete old scans:

```sql
-- Delete scans older than 90 days
DELETE FROM scans WHERE created_at < NOW() - INTERVAL '90 days';
```

### 4. Authentication on Endpoints

By default, endpoints are public. To require Firebase auth:

```python
@app.post("/api/v1/scan/leaks", ...)
async def start_s3_leak_scan(
    request: S3LeakScanRequest,
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(require_auth),  # ← Add this
) -> S3ScanInitResponse:
```

---

## Next Steps

1. **Test locally** with the curl commands above
2. **Monitor logs** in `backend.log` for issues
3. **Query PostgreSQL** to inspect found buckets
4. **Deploy to production** using Docker or Kubernetes
5. **Integrate with frontend** (call POST /api/v1/scan/leaks from your UI)

---

## Support & Debugging

For issues, check:

1. **Server logs:** `pytest --log-cli-level=DEBUG backend/test_s3_hunter.py`
2. **DB logs:** Connect to Neon and run:
   ```sql
   SELECT * FROM scans ORDER BY created_at DESC LIMIT 10;
   ```
3. **Network logs:** Add tcpdump to monitor S3 HTTPS connections
   ```bash
   tcpdump -i eth0 'tcp port 443 and host s3.amazonaws.com'
   ```

---

**Last updated:** April 11, 2026
