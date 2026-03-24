from typing import Any, Dict, List
from .client import get_client


def execute_sql(sql: str) -> List[Dict[str, Any]]:
    """Execute a SQL string against BigQuery and return rows as a list of dicts."""
    client = get_client()
    query_job = client.query(sql)
    results = query_job.result()
    return [dict(row) for row in results]
