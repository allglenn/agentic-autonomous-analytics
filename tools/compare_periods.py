import asyncio
from typing import Any, Dict, List
from semantic_layer.resolver import resolve_query
from bigquery.executor import execute_sql_async


async def compare_periods(
    metric: str,
    dimensions: List[str],
    period_1: str,
    period_2: str,
) -> Dict[str, Any]:
    """
    Compare a metric across two time periods.

    Args:
        metric: The business metric to compare.
        dimensions: Dimensions to group by.
        period_1: First time range (e.g. 'last_7_days').
        period_2: Second time range to compare against (e.g. 'previous_7_days').

    Returns:
        Dictionary with results for both periods and a delta summary.
    """
    sql_1 = resolve_query(metric=metric, dimensions=dimensions, time_range=period_1)
    sql_2 = resolve_query(metric=metric, dimensions=dimensions, time_range=period_2)

    rows_1, rows_2 = await asyncio.gather(
        execute_sql_async(sql_1),
        execute_sql_async(sql_2),
    )

    return {
        "metric": metric,
        "dimensions": dimensions,
        "period_1": {"time_range": period_1, "rows": rows_1},
        "period_2": {"time_range": period_2, "rows": rows_2},
    }
