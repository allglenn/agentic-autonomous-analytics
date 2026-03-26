from typing import List
from config.guardrails import guardrails
from config.settings import settings
from .metrics import METRICS
from .dimensions import DIMENSIONS

# Table → fully qualified BigQuery table name
TABLE_MAP = {
    "orders":      f"`{{project}}.{{dataset}}.orders`",
    "order_items": f"`{{project}}.{{dataset}}.order_items`",
    "sessions":    f"`{{project}}.{{dataset}}.sessions`",
}

# Time range → SQL WHERE clause per source table
TIME_RANGE_FILTERS = {
    "today": "DATE(created_at) = CURRENT_DATE()",
    "last_7_days": "DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)",
    "last_30_days": "DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)",
    "last_90_days": "DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)",
    "this_week": "DATE_TRUNC(DATE(created_at), WEEK) = DATE_TRUNC(CURRENT_DATE(), WEEK)",
    "this_month": "DATE_TRUNC(DATE(created_at), MONTH) = DATE_TRUNC(CURRENT_DATE(), MONTH)",
    "this_quarter": "DATE_TRUNC(DATE(created_at), QUARTER) = DATE_TRUNC(CURRENT_DATE(), QUARTER)",
    "this_year": "DATE_TRUNC(DATE(created_at), YEAR) = DATE_TRUNC(CURRENT_DATE(), YEAR)",
    "previous_7_days": (
        "DATE(created_at) BETWEEN "
        "DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY) AND "
        "DATE_SUB(CURRENT_DATE(), INTERVAL 8 DAY)"
    ),
    "previous_30_days": (
        "DATE(created_at) BETWEEN "
        "DATE_SUB(CURRENT_DATE(), INTERVAL 60 DAY) AND "
        "DATE_SUB(CURRENT_DATE(), INTERVAL 31 DAY)"
    ),
    "previous_month": (
        "DATE_TRUNC(DATE(created_at), MONTH) = "
        "DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH)"
    ),
    "previous_quarter": (
        "DATE_TRUNC(DATE(created_at), QUARTER) = "
        "DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 QUARTER), QUARTER)"
    ),
}


def resolve_query(metric: str, dimensions: List[str], time_range: str) -> str:
    """Translate a semantic metric request into a BigQuery SQL string."""

    # ── Guardrail checks ───────────────────────────────────────────────────
    if metric not in guardrails.allowed_metrics:
        raise ValueError(f"Metric '{metric}' is not in the allowed list.")

    for dim in dimensions:
        if dim in guardrails.blocked_dimensions:
            raise ValueError(f"Dimension '{dim}' is blocked (PII protection).")
        if dim not in guardrails.allowed_dimensions:
            raise ValueError(f"Dimension '{dim}' is not in the allowed list.")

    if time_range not in TIME_RANGE_FILTERS:
        raise ValueError(
            f"Unknown time_range: '{time_range}'. "
            f"Valid options: {list(TIME_RANGE_FILTERS.keys())}"
        )

    # ── Resolve metric and dimensions ──────────────────────────────────────
    metric_def = METRICS[metric]
    dim_defs = [DIMENSIONS[d] for d in dimensions]

    # Resolve source table — metric wins, dimensions must be compatible
    source_table = metric_def.source_table
    for dim in dim_defs:
        if dim.source_table != source_table:
            raise ValueError(
                f"Dimension '{dim}' is from table '{dim.source_table}' "
                f"but metric '{metric}' is from '{source_table}'. "
                f"Use drill_down to combine across tables."
            )

    # ── Build SQL ──────────────────────────────────────────────────────────
    project = settings.google_cloud_project
    dataset = settings.bigquery_dataset
    table = TABLE_MAP[source_table].format(project=project, dataset=dataset)

    dim_columns = [d.column for d in dim_defs]
    select_dims = (", ".join(dim_columns) + ", ") if dim_columns else ""
    group_by = ("GROUP BY " + ", ".join(dim_columns)) if dim_columns else ""
    date_filter = TIME_RANGE_FILTERS[time_range]

    sql = (
        f"SELECT\n"
        f"  {select_dims}{metric_def.expression} AS {metric}\n"
        f"FROM {table}\n"
        f"WHERE {date_filter}\n"
        f"{group_by}\n"
        f"LIMIT {guardrails.max_query_rows}"
    ).strip()

    return sql
