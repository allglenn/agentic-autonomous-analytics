from typing import Dict
from dataclasses import dataclass


@dataclass
class Metric:
    expression: str    # SQL aggregate expression
    source_table: str  # primary table this metric is computed from
    description: str


# Metric registry
# source_table values: "orders", "order_items", "sessions"
METRICS: Dict[str, Metric] = {
    # ── Revenue ────────────────────────────────────────────────────────────
    "revenue": Metric(
        expression="SUM(amount)",
        source_table="orders",
        description="Total revenue from completed orders",
    ),
    "refund_amount": Metric(
        expression="SUM(CASE WHEN status = 'refunded' THEN amount ELSE 0 END)",
        source_table="orders",
        description="Total value of refunded orders",
    ),
    "net_revenue": Metric(
        expression="SUM(CASE WHEN status != 'refunded' THEN amount ELSE 0 END)",
        source_table="orders",
        description="Revenue minus refunds",
    ),
    "shipping_cost": Metric(
        expression="SUM(shipping_cost)",
        source_table="orders",
        description="Total shipping costs charged",
    ),

    # ── Orders ─────────────────────────────────────────────────────────────
    "orders": Metric(
        expression="COUNT(DISTINCT order_id)",
        source_table="orders",
        description="Number of orders placed",
    ),
    "average_order_value": Metric(
        expression="SAFE_DIVIDE(SUM(amount), COUNT(DISTINCT order_id))",
        source_table="orders",
        description="Average revenue per order",
    ),
    "cancellation_rate": Metric(
        expression=(
            "SAFE_DIVIDE("
            "COUNT(DISTINCT CASE WHEN status = 'cancelled' THEN order_id END),"
            "COUNT(DISTINCT order_id)"
            ")"
        ),
        source_table="orders",
        description="Share of orders that were cancelled",
    ),
    "refund_rate": Metric(
        expression=(
            "SAFE_DIVIDE("
            "COUNT(DISTINCT CASE WHEN status = 'refunded' THEN order_id END),"
            "COUNT(DISTINCT order_id)"
            ")"
        ),
        source_table="orders",
        description="Share of orders that were refunded",
    ),

    # ── Customers ──────────────────────────────────────────────────────────
    "new_customers": Metric(
        expression="COUNT(DISTINCT CASE WHEN is_first_order = TRUE THEN customer_id END)",
        source_table="orders",
        description="Customers placing their first order",
    ),
    "repeat_customers": Metric(
        expression="COUNT(DISTINCT CASE WHEN is_first_order = FALSE THEN customer_id END)",
        source_table="orders",
        description="Customers with more than one order",
    ),
    "unique_customers": Metric(
        expression="COUNT(DISTINCT customer_id)",
        source_table="orders",
        description="Total distinct customers who ordered",
    ),

    # ── Products / Items ───────────────────────────────────────────────────
    "units_sold": Metric(
        expression="SUM(quantity)",
        source_table="order_items",
        description="Total units sold across all orders",
    ),
    "items_per_order": Metric(
        expression="SAFE_DIVIDE(SUM(quantity), COUNT(DISTINCT order_id))",
        source_table="order_items",
        description="Average number of items per order",
    ),

    # ── Sessions / Traffic ─────────────────────────────────────────────────
    "sessions": Metric(
        expression="COUNT(DISTINCT session_id)",
        source_table="sessions",
        description="Total website sessions",
    ),
    "conversion_rate": Metric(
        expression=(
            "SAFE_DIVIDE("
            "COUNT(DISTINCT CASE WHEN converted = TRUE THEN session_id END),"
            "COUNT(DISTINCT session_id)"
            ")"
        ),
        source_table="sessions",
        description="Share of sessions that resulted in an order",
    ),
    "bounce_rate": Metric(
        expression=(
            "SAFE_DIVIDE("
            "COUNT(DISTINCT CASE WHEN pages_viewed = 1 THEN session_id END),"
            "COUNT(DISTINCT session_id)"
            ")"
        ),
        source_table="sessions",
        description="Share of sessions that viewed only one page",
    ),
    "add_to_cart_rate": Metric(
        expression=(
            "SAFE_DIVIDE("
            "COUNT(DISTINCT CASE WHEN added_to_cart = TRUE THEN session_id END),"
            "COUNT(DISTINCT session_id)"
            ")"
        ),
        source_table="sessions",
        description="Share of sessions that added an item to cart",
    ),
}
