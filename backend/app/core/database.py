"""
app/core/database.py — PostgreSQL async connection pool + schema + logging helper
"""
from __future__ import annotations

import json
import logging
import os
import ssl
import uuid
from typing import Any, Dict, Optional

import asyncpg
from app.core.config import DATABASE_URL

logger = logging.getLogger("database")

_db_pool: Optional[asyncpg.Pool] = None

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS osint_logs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id       UUID NOT NULL,
    module        TEXT NOT NULL,
    target        TEXT NOT NULL,
    result_json   JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_uid      TEXT
);

CREATE INDEX IF NOT EXISTS idx_osint_logs_module  ON osint_logs (module);
CREATE INDEX IF NOT EXISTS idx_osint_logs_target  ON osint_logs (target);
CREATE INDEX IF NOT EXISTS idx_osint_logs_created ON osint_logs (created_at DESC);
"""


def get_db_pool() -> Optional[asyncpg.Pool]:
    return _db_pool


async def init_db() -> None:
    """Create the connection pool and apply the schema. Fails gracefully."""
    global _db_pool
    try:
        ssl_ctx: Any = None
        if "sslmode=require" in DATABASE_URL or "sslmode=verify-full" in DATABASE_URL:
            ssl_ctx = ssl.create_default_context()

        _db_pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30,
            ssl=ssl_ctx,
            statement_cache_size=0,  # PgBouncer compatibility
        )
        async with _db_pool.acquire() as conn:
            await conn.execute(_SCHEMA_SQL)
        logger.info("PostgreSQL pool ready (SSL=%s).", bool(ssl_ctx))
    except Exception as exc:
        logger.error("PostgreSQL pool FAILED: %s", exc)
        _db_pool = None


async def close_db() -> None:
    global _db_pool
    if _db_pool is not None:
        await _db_pool.close()
        _db_pool = None
        logger.info("PostgreSQL pool closed.")


async def log_to_db(
    module: str,
    target: str,
    scan_id: str,
    result: Dict[str, Any],
    user_uid: Optional[str] = None,
) -> None:
    """Fire-and-forget INSERT into osint_logs."""
    if _db_pool is None:
        logger.warning("DB unavailable — skipping log for scan_id=%s", scan_id)
        return
    try:
        async with _db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO osint_logs (scan_id, module, target, result_json, user_uid)
                VALUES ($1, $2, $3, $4::jsonb, $5)
                """,
                uuid.UUID(scan_id), module, target, json.dumps(result), user_uid,
            )
        logger.info("DB logged scan_id=%s module=%s", scan_id, module)
    except Exception as exc:
        logger.error("DB insert failed for scan_id=%s: %s", scan_id, exc)
