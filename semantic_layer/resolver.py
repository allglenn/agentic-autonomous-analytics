from typing import List
from config.guardrails import guardrails
from config.settings import settings
from .metrics import METRICS
from .dimensions import DIMENSIONS


def resolve_query(metric: str, dimensions: List[str], time_range: str) -> str:
    """Translate a semantic metric request into a BigQuery SQL string."""
    if metric not in guardrails.allowed_metrics:
        raise ValueError(f"Metric '{metric}' is not in the allowed list.")

    for dim in dimensions:
        if dim in guardrails.blocked_dimensions:
            raise ValueError(f"Dimension '{dim}' is blocked (PII protection).")
        if dim not in guardrails.allowed_dimensions:
            raise ValueError(f"Dimension '{dim}' is not in the allowed list.")

    metric_expr = METRICS[metric]
    dim_columns = [DIMENSIONS[d] for d in dimensions]
    select_dims = ", ".join(dim_columns)
    group_by = ", ".join(dim_columns)

    date_filter = _resolve_time_range(time_range)

    sql = f"""
SELECT
  {select_dims},
  {metric_expr} AS {metric}
FROM `{settings.google_cloud_project}.{settings.bigquery_dataset}.orders`
WHERE {date_filter}
GROUP BY {group_by}
LIMIT {guardrails.max_query_rows}
""".strip()

    return sql


def _resolve_time_range(time_range: str) -> str:
    filters = {
        "today": "DATE(created_at) = CURRENT_DATE()",
        "last_7_days": "DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)",
        "last_30_days": "DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)",
        "this_month": "DATE_TRUNC(DATE(created_at), MONTH) = DATE_TRUNC(CURRENT_DATE(), MONTH)",
        "previous_7_days": (
            "DATE(created_at) BETWEEN "
            "DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY) AND "
            "DATE_SUB(CURRENT_DATE(), INTERVAL 8 DAY)"
        ),
    }
    if time_range not in filters:
        raise ValueError(f"Unknown time_range: '{time_range}'")
    return filters[time_range]
