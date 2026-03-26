from typing import List
from pydantic import BaseModel


class Guardrails(BaseModel):
    allowed_metrics: List[str] = [
        # Revenue
        "revenue",
        "refund_amount",
        "net_revenue",
        "shipping_cost",
        # Orders
        "orders",
        "average_order_value",
        "cancellation_rate",
        "refund_rate",
        # Customers
        "new_customers",
        "repeat_customers",
        "unique_customers",
        # Products
        "units_sold",
        "items_per_order",
        # Sessions / Traffic
        "sessions",
        "conversion_rate",
        "bounce_rate",
        "add_to_cart_rate",
    ]

    allowed_dimensions: List[str] = [
        # Channel
        "channel",
        "traffic_source",
        "campaign",
        "utm_medium",
        # Geography
        "country",
        "region",
        "city",
        # Product
        "product_category",
        "brand",
        "product_name",
        # Customer
        "customer_segment",
        "customer_type",
        # Device
        "device",
        "device_os",
        # Time
        "day",
        "week",
        "month",
        # Promotion
        "promotion_code",
        "discount_type",
        # Order
        "order_status",
        "payment_method",
    ]

    # PII fields — never exposed to the agent
    blocked_dimensions: List[str] = [
        "user_id",
        "customer_id",
        "email",
        "phone",
        "ip_address",
        "full_name",
        "address",
    ]

    max_query_rows: int = 10_000       # BigQuery cost control
    max_executor_steps: int = 10       # ReAct loop hard limit


guardrails = Guardrails()
