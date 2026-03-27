import asyncio
import math
from typing import Any, Dict, List, Optional
from semantic_layer.resolver import resolve_query
from semantic_layer.dimensions import DIMENSIONS
from bigquery.executor import execute_sql_async


def _pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    return cov / (sx * sy)


def _interpret(r: Optional[float]) -> str:
    if r is None:
        return "insufficient data"
    if r > 0.7:
        return "strong positive"
    if r > 0.3:
        return "moderate positive"
    if r > 0:
        return "weak positive"
    if r > -0.3:
        return "weak negative"
    if r > -0.7:
        return "moderate negative"
    return "strong negative"


async def correlate(
    metric_a: str,
    metric_b: str,
    dimension: str,
    time_range: str,
) -> Dict[str, Any]:
    """
    Compute Pearson correlation between two metrics across segments of a shared dimension.

    Both metrics must be compatible with the given dimension (same source table).
    Use this to ask: "Do channels with more sessions also generate more revenue?"

    Args:
        metric_a: First metric (e.g. 'sessions').
        metric_b: Second metric (e.g. 'orders').
        dimension: Shared dimension to segment by (e.g. 'channel').
                   Must be valid for both metrics' source tables.
        time_range: Time range for both metrics (e.g. 'this_quarter').

    Returns:
        Pearson correlation coefficient, interpretation, and per-segment data.
    """
    sql_a = resolve_query(metric=metric_a, dimensions=[dimension], time_range=time_range)
    sql_b = resolve_query(metric=metric_b, dimensions=[dimension], time_range=time_range)

    rows_a, rows_b = await asyncio.gather(
        execute_sql_async(sql_a),
        execute_sql_async(sql_b),
    )

    dim_col = DIMENSIONS[dimension].column if dimension in DIMENSIONS else dimension

    def _val(row: dict, col: str, fallback: str) -> Any:
        return row.get(col) or row.get(fallback)

    map_a = {_val(r, dim_col, dimension): r.get(metric_a) or 0 for r in rows_a}
    map_b = {_val(r, dim_col, dimension): r.get(metric_b) or 0 for r in rows_b}

    shared = sorted(set(map_a) & set(map_b), key=lambda x: str(x))

    if not shared:
        return {
            "metric_a": metric_a,
            "metric_b": metric_b,
            "dimension": dimension,
            "time_range": time_range,
            "correlation": None,
            "interpretation": "no shared segments — metrics may come from incompatible tables",
            "data_points": [],
        }

    xs = [map_a[s] for s in shared]
    ys = [map_b[s] for s in shared]
    r = _pearson(xs, ys)

    data_points = [
        {"segment": s, metric_a: round(xs[i], 4), metric_b: round(ys[i], 4)}
        for i, s in enumerate(shared)
    ]

    return {
        "metric_a": metric_a,
        "metric_b": metric_b,
        "dimension": dimension,
        "time_range": time_range,
        "correlation": round(r, 4) if r is not None else None,
        "interpretation": _interpret(r),
        "data_points": data_points,
    }
