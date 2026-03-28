import asyncio
import hashlib
import json
import logging
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from .client import get_client
from config.settings import settings

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300  # 5 minutes

# In-memory fallback cache: used when REDIS_URL is not configured.
# sql_hash → (rows, timestamp)
_local_cache: Dict[str, Tuple[List[Dict[str, Any]], float]] = {}

# Redis client — initialised once on first use, None if REDIS_URL is unset.
_redis: Optional[Any] = None


def _get_redis() -> Optional[Any]:
    """Return a Redis client if REDIS_URL is configured, else None."""
    global _redis
    if _redis is not None:
        return _redis
    if not settings.redis_url:
        return None
    try:
        import redis as redis_lib
        _redis = redis_lib.from_url(settings.redis_url, decode_responses=True)
        logger.info("[bigquery] redis_cache_enabled url=%s", settings.redis_url)
    except Exception:
        logger.warning("[bigquery] redis_unavailable — falling back to in-memory cache")
        _redis = None
    return _redis


def _cache_get(key: str) -> Optional[List[Dict[str, Any]]]:
    r = _get_redis()
    if r is not None:
        try:
            raw = r.get(key)
            if raw:
                return json.loads(raw)
            return None
        except Exception:
            logger.warning("[bigquery] redis_get_failed key=%s — falling back to local cache", key[:8])
    # in-memory fallback
    rows, cached_at = _local_cache.get(key, (None, 0.0))
    if rows is not None and (time.monotonic() - cached_at) < CACHE_TTL_SECONDS:
        return rows
    return None


def _cache_set(key: str, rows: List[Dict[str, Any]]) -> None:
    r = _get_redis()
    if r is not None:
        try:
            r.setex(key, CACHE_TTL_SECONDS, json.dumps(rows))
            return
        except Exception:
            logger.warning("[bigquery] redis_set_failed key=%s — falling back to local cache", key[:8])
    _local_cache[key] = (rows, time.monotonic())


def execute_sql(sql: str) -> List[Dict[str, Any]]:
    """Execute a SQL string against BigQuery and return rows as a list of dicts."""
    cache_key = hashlib.md5(sql.encode()).hexdigest()
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.info("[bigquery] cache_hit key=%s rows=%d", cache_key[:8], len(cached))
        return cached

    started = time.monotonic()
    sql_preview = " ".join(sql.strip().split())[:220]
    logger.info(
        "[bigquery] query_start timeout=%ss sql=%s",
        settings.bigquery_query_timeout_seconds,
        sql_preview,
    )
    client = get_client()
    try:
        query_job = client.query(sql, timeout=settings.bigquery_query_timeout_seconds)
        results = query_job.result(timeout=settings.bigquery_query_timeout_seconds)
        rows = [
            {k: v.isoformat() if isinstance(v, (date, datetime)) else v for k, v in dict(row).items()}
            for row in results
        ]
        logger.info(
            "[bigquery] query_done rows=%d elapsed=%.2fs",
            len(rows),
            time.monotonic() - started,
        )
        _cache_set(cache_key, rows)
        return rows
    except Exception:
        logger.exception(
            "[bigquery] query_failed elapsed=%.2fs",
            time.monotonic() - started,
        )
        raise


async def execute_sql_async(sql: str) -> List[Dict[str, Any]]:
    """Async wrapper — checks cache first, then runs the query in a thread."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(execute_sql, sql),
            timeout=settings.bigquery_query_timeout_seconds,
        )
    except asyncio.TimeoutError:
        raise RuntimeError(
            f"BigQuery query timed out after {settings.bigquery_query_timeout_seconds}s"
        )
