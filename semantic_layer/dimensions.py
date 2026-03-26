from typing import Dict
from dataclasses import dataclass


@dataclass
class Dimension:
    column: str        # SQL column name in the source table
    source_table: str  # table this dimension lives in
    description: str


# Dimension registry
DIMENSIONS: Dict[str, Dimension] = {
    # ── Channel / Traffic ──────────────────────────────────────────────────
    "channel": Dimension(
        column="marketing_channel",
        source_table="orders",
        description="Acquisition channel (organic, paid, email, social, direct)",
    ),
    "traffic_source": Dimension(
        column="traffic_source",
        source_table="sessions",
        description="Traffic source of the session",
    ),
    "campaign": Dimension(
        column="utm_campaign",
        source_table="orders",
        description="UTM campaign name",
    ),
    "utm_medium": Dimension(
        column="utm_medium",
        source_table="orders",
        description="UTM medium (cpc, email, social…)",
    ),

    # ── Geography ──────────────────────────────────────────────────────────
    "country": Dimension(
        column="shipping_country",
        source_table="orders",
        description="Destination country of the order",
    ),
    "region": Dimension(
        column="shipping_region",
        source_table="orders",
        description="Destination region / state",
    ),
    "city": Dimension(
        column="shipping_city",
        source_table="orders",
        description="Destination city",
    ),

    # ── Product ────────────────────────────────────────────────────────────
    "product_category": Dimension(
        column="product_category",
        source_table="order_items",
        description="Top-level product category",
    ),
    "brand": Dimension(
        column="brand",
        source_table="order_items",
        description="Product brand",
    ),
    "product_name": Dimension(
        column="product_name",
        source_table="order_items",
        description="Individual product name",
    ),

    # ── Customer ───────────────────────────────────────────────────────────
    "customer_segment": Dimension(
        column="customer_segment",
        source_table="orders",
        description="Customer segment (VIP, regular, at-risk, churned…)",
    ),
    "customer_type": Dimension(
        column="CASE WHEN is_first_order THEN 'new' ELSE 'returning' END",
        source_table="orders",
        description="New vs returning customer",
    ),

    # ── Device ─────────────────────────────────────────────────────────────
    "device": Dimension(
        column="device_type",
        source_table="orders",
        description="Device type (mobile, desktop, tablet)",
    ),
    "device_os": Dimension(
        column="device_os",
        source_table="sessions",
        description="Operating system of the session device",
    ),

    # ── Time ───────────────────────────────────────────────────────────────
    "day": Dimension(
        column="DATE(created_at)",
        source_table="orders",
        description="Day of the order",
    ),
    "week": Dimension(
        column="DATE_TRUNC(DATE(created_at), WEEK)",
        source_table="orders",
        description="Week of the order",
    ),
    "month": Dimension(
        column="DATE_TRUNC(DATE(created_at), MONTH)",
        source_table="orders",
        description="Month of the order",
    ),

    # ── Promotion ──────────────────────────────────────────────────────────
    "promotion_code": Dimension(
        column="coupon_code",
        source_table="orders",
        description="Discount / coupon code applied",
    ),
    "discount_type": Dimension(
        column="discount_type",
        source_table="orders",
        description="Type of discount applied (percentage, fixed, free_shipping…)",
    ),

    # ── Order ──────────────────────────────────────────────────────────────
    "order_status": Dimension(
        column="status",
        source_table="orders",
        description="Order status (completed, cancelled, refunded, pending)",
    ),
    "payment_method": Dimension(
        column="payment_method",
        source_table="orders",
        description="Payment method used (card, paypal, bnpl…)",
    ),
}
