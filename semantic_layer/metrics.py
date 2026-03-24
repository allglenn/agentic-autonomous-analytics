from typing import Dict

# metric_name → SQL expression
METRICS: Dict[str, str] = {
    "revenue": "SUM(amount)",
    "orders": "COUNT(DISTINCT order_id)",
    "sessions": "COUNT(DISTINCT session_id)",
    "conversion_rate": "SAFE_DIVIDE(COUNT(DISTINCT order_id), COUNT(DISTINCT session_id))",
    "average_order_value": "SAFE_DIVIDE(SUM(amount), COUNT(DISTINCT order_id))",
}
