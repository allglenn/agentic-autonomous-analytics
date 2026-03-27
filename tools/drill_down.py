import asyncio
from typing import Any, Dict, List
from semantic_layer.resolver import resolve_query
from bigquery.executor import execute_sql


async def drill_down(
    metric: str,
    current_dimensions: List[str],
    new_dimension: str,
    time_range: str,
) -> Dict[str, Any]:
    """
    Drill down by adding a new dimension to an existing query context.

    Args:
        metric: The business metric to query.
        current_dimensions: Existing dimensions already in the analysis.
        new_dimension: The new dimension to segment by.
        time_range: Time range for the query.

    Returns:
        Query result with the expanded dimension set.
    """
    dimensions = current_dimensions + [new_dimension]
    sql = resolve_query(metric=metric, dimensions=dimensions, time_range=time_range)
    rows = await asyncio.to_thread(execute_sql, sql)
    return {
        "metric": metric,
        "dimensions": dimensions,
        "new_dimension": new_dimension,
        "time_range": time_range,
        "rows": rows,
        "row_count": len(rows),
    }
