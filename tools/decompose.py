import asyncio
from typing import Any, Dict
from semantic_layer.resolver import resolve_query
from semantic_layer.dimensions import DIMENSIONS
from bigquery.executor import execute_sql_async


async def decompose(
    metric: str,
    dimension: str,
    period_1: str,
    period_2: str,
) -> Dict[str, Any]:
    """
    Break down how each segment of a dimension contributed to a metric change.

    Args:
        metric: The business metric to decompose (e.g. 'revenue', 'new_customers').
        dimension: The dimension to segment by (e.g. 'channel', 'product_category').
        period_1: Current period (e.g. 'this_quarter').
        period_2: Comparison period (e.g. 'previous_quarter').

    Returns:
        Dictionary with per-segment values, absolute delta, and % contribution to
        the total change for each segment — sorted by largest absolute contribution.
    """
    sql_1 = resolve_query(metric=metric, dimensions=[dimension], time_range=period_1)
    sql_2 = resolve_query(metric=metric, dimensions=[dimension], time_range=period_2)

    rows_1, rows_2 = await asyncio.gather(
        execute_sql_async(sql_1),
        execute_sql_async(sql_2),
    )

    # SQL column name may differ from semantic name (e.g. 'channel' → 'marketing_channel')
    dim_col = DIMENSIONS[dimension].column if dimension in DIMENSIONS else dimension

    def _val(row: dict, col: str, fallback: str) -> Any:
        return row.get(col) or row.get(fallback)

    p1_map = {_val(r, dim_col, dimension): r.get(metric) or 0 for r in rows_1}
    p2_map = {_val(r, dim_col, dimension): r.get(metric) or 0 for r in rows_2}

    all_segments = sorted(set(p1_map) | set(p2_map), key=lambda x: str(x))
    total_p1 = sum(p1_map.values())
    total_p2 = sum(p2_map.values())
    total_delta = total_p1 - total_p2

    segments = []
    for seg in all_segments:
        v1 = p1_map.get(seg, 0)
        v2 = p2_map.get(seg, 0)
        delta = v1 - v2
        contribution_pct = round(delta / total_delta * 100, 1) if total_delta else 0.0
        segments.append({
            "segment": seg,
            period_1: round(v1, 4),
            period_2: round(v2, 4),
            "delta": round(delta, 4),
            "contribution_pct": contribution_pct,
        })

    segments.sort(key=lambda x: abs(x["contribution_pct"]), reverse=True)

    return {
        "metric": metric,
        "dimension": dimension,
        "period_1": period_1,
        "period_2": period_2,
        "total": {
            period_1: round(total_p1, 4),
            period_2: round(total_p2, 4),
            "delta": round(total_delta, 4),
        },
        "segments": segments,
    }
