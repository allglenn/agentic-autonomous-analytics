from typing import List
from pydantic import BaseModel


class Guardrails(BaseModel):
    allowed_metrics: List[str] = [
        "revenue",
        "orders",
        "sessions",
        "conversion_rate",
        "average_order_value",
    ]
    allowed_dimensions: List[str] = [
        "channel",
        "country",
        "campaign",
        "device",
        "product_category",
    ]
    # PII fields — never exposed to the agent
    blocked_dimensions: List[str] = [
        "user_id",
        "email",
        "phone",
        "ip_address",
    ]
    max_query_rows: int = 10_000       # BigQuery cost control
    max_executor_steps: int = 10       # ReAct loop hard limit


guardrails = Guardrails()
