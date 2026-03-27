import asyncio
import logging
import time
from datetime import date, datetime
from typing import Any, Dict, List
from .client import get_client
from config.settings import settings

logger = logging.getLogger(__name__)


def execute_sql(sql: str) -> List[Dict[str, Any]]:
    """Execute a SQL string against BigQuery and return rows as a list of dicts."""
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
        return rows
    except Exception:
        logger.exception(
            "[bigquery] query_failed elapsed=%.2fs",
            time.monotonic() - started,
        )
        raise


async def execute_sql_async(sql: str) -> List[Dict[str, Any]]:
    """Async wrapper with a hard asyncio-level timeout."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(execute_sql, sql),
            timeout=settings.bigquery_query_timeout_seconds,
        )
    except asyncio.TimeoutError:
        raise RuntimeError(
            f"BigQuery query timed out after {settings.bigquery_query_timeout_seconds}s"
        )
