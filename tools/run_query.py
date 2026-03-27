import asyncio
from typing import Any, Dict, List
from semantic_layer.resolver import resolve_query
from bigquery.executor import execute_sql


async def run_query(metric: str, dimensions: List[str], time_range: str) -> Dict[str, Any]:
    """
    Run a metric query via the semantic layer.

    Args:
        metric: The business metric to query (e.g. 'revenue', 'orders').
        dimensions: List of dimensions to group by (e.g. ['channel', 'country']).
        time_range: Time range string (e.g. 'last_7_days', 'today').

    Returns:
        Dictionary with metric, dimensions, time_range, and rows.
    """
    sql = resolve_query(metric=metric, dimensions=dimensions, time_range=time_range)
    rows = await asyncio.to_thread(execute_sql, sql)
    return {
        "metric": metric,
        "dimensions": dimensions,
        "time_range": time_range,
        "rows": rows,
        "row_count": len(rows),
    }
