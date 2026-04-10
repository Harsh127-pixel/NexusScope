"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     NexusScope — Background Workers                         ║
║           Long-running async tasks triggered by FastAPI endpoints           ║
╚══════════════════════════════════════════════════════════════════════════════╝

RESPONSIBILITIES
────────────────
 ✓  Orchestrate background OSINT scans
 ✓  Manage task lifecycle (insert → execute → update)
 ✓  Handle errors gracefully and log status
 ✓  Update PostgreSQL with real-time progress

EXECUTION MODEL
───────────────
FastAPI BackgroundTasks runs workers in the lifespan:
  1. HTTP endpoint receives request
  2. Endpoint extracts parameters (domain, type, etc.)
  3. Endpoint calls add_task(worker_function, ...)
  4. Worker function runs concurrently
  5. Database is updated with results
  6. No blocking; HTTP response returns immediately

WORKERS
───────
  • run_leak_scan(task_id, domain)
      Hunts for exposed S3 buckets associated with domain
      Inserts scan record → executes hunt_s3_buckets → updates DB

USAGE
─────
From a FastAPI endpoint:
    background_tasks = BackgroundTasks()
    task_id = uuid.uuid4()
    background_tasks.add_task(run_leak_scan, task_id, domain)
    return {"task_id": str(task_id), "message": "Scan started"}
"""

import asyncio
import logging
from uuid import UUID

from database import insert_scan, update_scan_results
from app.modules.s3_hunter import hunt_s3_buckets

logger = logging.getLogger("workers")


# ─────────────────────────────────────────────
#  §1  S3 LEAK HUNTING WORKER
#  ─────────────────────────────────────────────
async def run_leak_scan(task_id: UUID, domain: str) -> None:
    """
    Background worker: Orchestrates an S3 bucket leak scanning task.
    
    WORKFLOW:
      1. Insert scan record into DB with status='running'
      2. Await hunt_s3_buckets(domain) — this is async and may take 30-50 seconds
      3. Update DB with status='completed' and results dictionary
      4. If error occurs, catch exception and update DB with status='failed'
    
    DATABASE UPDATES:
      • INSERT: scan(id, target_domain='example.com', status='running', results='{}')
      • UPDATE: status='completed', results={"domain": "...", "buckets_found": {...}}
      • UPDATE (on error): status='failed', results={"error": "message"}
    
    PARAMS:
        task_id: UUID for this scan task (provided by HTTP endpoint)
        domain: Target domain to scan (e.g., "example.com")
    
    RAISES:
        asyncpg.PostgresError: If database operations fail (connection lost, etc.)
        asyncio.TimeoutError: If hunt_s3_buckets exceeds overall timeout
    
    LOGGING:
        • INFO: Task started, completed
        • WARNING: Open buckets discovered
        • ERROR: Scan failed, DB update failed
    
    USAGE:
        import asyncio
        from uuid import uuid4
        from workers import run_leak_scan
        
        task_id = uuid4()
        await run_leak_scan(task_id, "example.com")
    """
    try:
        logger.info(f"Starting S3 leak scan task_id={task_id} domain={domain}")
        
        # ── Step 1: Create scan record in DB ────────────────────
        try:
            await insert_scan(task_id, domain)
        except Exception as e:
            logger.error(f"Failed to insert scan record: {e}")
            raise
        
        # ── Step 2: Execute S3 hunting (30-50 seconds) ──────────
        logger.info(f"Executing S3 bucket hunt for {domain}...")
        
        try:
            # wrap in timeout to prevent hanging
            results = await asyncio.wait_for(
                hunt_s3_buckets(domain),
                timeout=120  # Max 2 minutes for hunt operation
            )
        except asyncio.TimeoutError:
            logger.error(f"S3 hunt timed out for {domain}")
            await update_scan_results(
                task_id,
                "failed",
                {"error": "Hunt operation exceeded 120 second timeout"}
            )
            return
        
        # ── Step 3: Update DB with results ─────────────────────
        logger.info(
            f"S3 hunt completed: {len(results['buckets_found']['open'])} "
            f"open buckets found"
        )
        
        try:
            await update_scan_results(task_id, "completed", results)
        except Exception as e:
            logger.error(f"Failed to update scan results in DB: {e}")
            # Still mark as failed even if DB update fails
            try:
                await update_scan_results(
                    task_id,
                    "failed",
                    {"error": f"Database update failed: {str(e)}"}
                )
            except:
                logger.error("Could not even update failure status in DB")
            raise
        
        logger.info(f"✓ S3 leak scan task completed: {task_id}")
    
    except Exception as e:
        logger.error(f"✗ S3 leak scan task failed: {task_id} — {type(e).__name__}: {e}")
        
        # Attempt to mark task as failed in DB
        try:
            await update_scan_results(
                task_id,
                "failed",
                {"error": f"{type(e).__name__}: {str(e)}"}
            )
        except Exception as db_error:
            logger.error(f"Could not update task status to failed in DB: {db_error}")


# ──────────────────────────────────────────────────────────────────────────────
#  Additional workers can be added here:
#    • run_dns_enumeration(task_id, domain)
#    • run_tech_stack_detect(task_id, url)
#    • run_vulnerability_scan(task_id, target)
#  All follow the same pattern: Insert → Execute → Update (or fail)
# ──────────────────────────────────────────────────────────────────────────────
