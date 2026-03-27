"""
Seed script — generates realistic ecommerce data and loads it into BigQuery.
Works with both the local BigQuery emulator and real GCP BigQuery.

Usage:
    python scripts/seed_data.py              # 1000 orders (default)
    python scripts/seed_data.py --orders 5000
"""

from dotenv import load_dotenv
load_dotenv()

import argparse
import os
import random
import uuid
from datetime import datetime, timedelta

from faker import Faker
from google.cloud import bigquery
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials

fake = Faker()
random.seed(42)
Faker.seed(42)

# ── Config ─────────────────────────────────────────────────────────────────
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "local-project")
DATASET = os.getenv("BIGQUERY_DATASET", "analytics")
EMULATOR = os.getenv("BIGQUERY_EMULATOR_HOST")

# ── Reference data ──────────────────────────────────────────────────────────
CHANNELS = ["organic", "paid_search", "email", "social", "direct", "affiliate"]
DEVICES = ["mobile", "desktop", "tablet"]
DEVICE_OS = {"mobile": ["iOS", "Android"], "desktop": ["Windows", "macOS", "Linux"], "tablet": ["iOS", "Android"]}
COUNTRIES = ["US", "UK", "FR", "DE", "CA", "AU", "ES", "IT", "NL", "BR"]
SEGMENTS = ["VIP", "regular", "new", "at_risk", "churned"]
STATUSES = ["completed", "completed", "completed", "cancelled", "refunded"]  # weighted
PAYMENT_METHODS = ["credit_card", "paypal", "apple_pay", "google_pay", "bnpl"]
DISCOUNT_TYPES = [None, None, None, "percentage", "fixed", "free_shipping"]
CATEGORIES = ["Electronics", "Clothing", "Home & Garden", "Sports", "Beauty", "Books", "Toys", "Food"]
BRANDS = {
    "Electronics": ["TechPro", "Nexus", "Volt"],
    "Clothing": ["UrbanWear", "StyleCo", "FitLine"],
    "Home & Garden": ["Homely", "GreenSpace", "NestCo"],
    "Sports": ["ActiveGear", "ProSport", "PeakFit"],
    "Beauty": ["GlowUp", "PureSkin", "LuxeBeauty"],
    "Books": ["PageTurn", "ReadMore", "Inkwell"],
    "Toys": ["FunZone", "PlayMaker", "KidsCo"],
    "Food": ["TastyBites", "FreshFarm", "GourmetCo"],
}
CAMPAIGNS = ["summer_sale", "black_friday", "new_year", "back_to_school", "flash_sale", None, None]
MEDIUMS = ["cpc", "email", "social", "organic", "referral"]
PRODUCTS = {
    cat: [f"{brand} {fake.word().capitalize()} {random.randint(100, 999)}"
          for brand in brands for _ in range(3)]
    for cat, brands in BRANDS.items()
}


def get_client() -> bigquery.Client:
    if EMULATOR:
        opts = ClientOptions(api_endpoint=f"http://{EMULATOR}")
        return bigquery.Client(project=PROJECT, client_options=opts,
                               credentials=AnonymousCredentials())
    return bigquery.Client(project=PROJECT)


def create_dataset(client: bigquery.Client):
    dataset_ref = bigquery.Dataset(f"{PROJECT}.{DATASET}")
    dataset_ref.location = "US"
    try:
        client.delete_dataset(dataset_ref, delete_contents=True, not_found_ok=True)
        print(f"  Dropped {PROJECT}.{DATASET}")
    except Exception as e:
        print(f"  Drop warning: {e}")
    try:
        client.create_dataset(dataset_ref)
        print(f"  Created {PROJECT}.{DATASET}")
    except Exception as e:
        print(f"  Create warning: {e}")


def create_tables(client: bigquery.Client):
    schemas = {
        "orders": [
            bigquery.SchemaField("order_id", "STRING"),
            bigquery.SchemaField("customer_id", "STRING"),
            bigquery.SchemaField("amount", "FLOAT"),
            bigquery.SchemaField("shipping_cost", "FLOAT"),
            bigquery.SchemaField("status", "STRING"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
            bigquery.SchemaField("marketing_channel", "STRING"),
            bigquery.SchemaField("utm_campaign", "STRING"),
            bigquery.SchemaField("utm_medium", "STRING"),
            bigquery.SchemaField("traffic_source", "STRING"),
            bigquery.SchemaField("shipping_country", "STRING"),
            bigquery.SchemaField("shipping_region", "STRING"),
            bigquery.SchemaField("shipping_city", "STRING"),
            bigquery.SchemaField("customer_segment", "STRING"),
            bigquery.SchemaField("is_first_order", "BOOLEAN"),
            bigquery.SchemaField("device_type", "STRING"),
            bigquery.SchemaField("coupon_code", "STRING"),
            bigquery.SchemaField("discount_type", "STRING"),
            bigquery.SchemaField("payment_method", "STRING"),
        ],
        "order_items": [
            bigquery.SchemaField("order_item_id", "STRING"),
            bigquery.SchemaField("order_id", "STRING"),
            bigquery.SchemaField("product_name", "STRING"),
            bigquery.SchemaField("product_category", "STRING"),
            bigquery.SchemaField("brand", "STRING"),
            bigquery.SchemaField("quantity", "INTEGER"),
            bigquery.SchemaField("unit_price", "FLOAT"),
            bigquery.SchemaField("refunded", "BOOLEAN"),
        ],
        "sessions": [
            bigquery.SchemaField("session_id", "STRING"),
            bigquery.SchemaField("customer_id", "STRING"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
            bigquery.SchemaField("device_type", "STRING"),
            bigquery.SchemaField("device_os", "STRING"),
            bigquery.SchemaField("traffic_source", "STRING"),
            bigquery.SchemaField("marketing_channel", "STRING"),
            bigquery.SchemaField("pages_viewed", "INTEGER"),
            bigquery.SchemaField("added_to_cart", "BOOLEAN"),
            bigquery.SchemaField("converted", "BOOLEAN"),
        ],
    }
    for name, schema in schemas.items():
        table_ref = f"{PROJECT}.{DATASET}.{name}"
        table = bigquery.Table(table_ref, schema=schema)
        client.create_table(table, exists_ok=True)
        print(f"  Table {name} ready")


def random_date(days_back: int = 90) -> datetime:
    return datetime.utcnow() - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )


def generate_data(n_orders: int):
    orders, order_items, sessions = [], [], []

    # Track first-order customers
    seen_customers: set = set()

    # Generate extra sessions (not all convert)
    n_sessions = int(n_orders * 3.5)
    session_customers = [str(uuid.uuid4()) for _ in range(n_sessions)]

    for i in range(n_sessions):
        cid = session_customers[i]
        device = random.choice(DEVICES)
        channel = random.choice(CHANNELS)
        converted = i < n_orders  # first n_orders sessions convert
        created_at = random_date(90)
        sessions.append({
            "session_id": str(uuid.uuid4()),
            "customer_id": cid,
            "created_at": created_at.isoformat(),
            "device_type": device,
            "device_os": random.choice(DEVICE_OS[device]),
            "traffic_source": channel,
            "marketing_channel": channel,
            "pages_viewed": random.randint(1, 20),
            "added_to_cart": converted or random.random() < 0.3,
            "converted": converted,
        })

    for i in range(n_orders):
        order_id = str(uuid.uuid4())
        customer_id = session_customers[i]
        is_first = customer_id not in seen_customers
        seen_customers.add(customer_id)

        channel = sessions[i]["marketing_channel"]
        campaign = random.choice(CAMPAIGNS)
        device = sessions[i]["device_type"]
        country = random.choice(COUNTRIES)
        status = random.choice(STATUSES)
        discount_type = random.choice(DISCOUNT_TYPES)
        created_at = random_date(90)

        # Generate 1-5 items per order
        n_items = random.randint(1, 5)
        total = 0.0
        for _ in range(n_items):
            category = random.choice(CATEGORIES)
            brand = random.choice(BRANDS[category])
            product = random.choice(PRODUCTS[category])
            qty = random.randint(1, 3)
            price = round(random.uniform(5.0, 300.0), 2)
            total += qty * price
            order_items.append({
                "order_item_id": str(uuid.uuid4()),
                "order_id": order_id,
                "product_name": product,
                "product_category": category,
                "brand": brand,
                "quantity": qty,
                "unit_price": price,
                "refunded": status == "refunded",
            })

        shipping = round(random.uniform(0, 15.0), 2) if discount_type != "free_shipping" else 0.0

        orders.append({
            "order_id": order_id,
            "customer_id": customer_id,
            "amount": round(total, 2),
            "shipping_cost": shipping,
            "status": status,
            "created_at": created_at.isoformat(),
            "marketing_channel": channel,
            "utm_campaign": campaign or "",
            "utm_medium": random.choice(MEDIUMS),
            "traffic_source": channel,
            "shipping_country": country,
            "shipping_region": fake.state() if country == "US" else fake.city(),
            "shipping_city": fake.city(),
            "customer_segment": random.choice(SEGMENTS),
            "is_first_order": is_first,
            "device_type": device,
            "coupon_code": fake.bothify("SAVE##") if discount_type else "",
            "discount_type": discount_type or "",
            "payment_method": random.choice(PAYMENT_METHODS),
        })

    return orders, order_items, sessions


def load(client: bigquery.Client, table: str, rows: list):
    table_ref = f"{PROJECT}.{DATASET}.{table}"
    errors = client.insert_rows_json(table_ref, rows)
    if errors:
        print(f"  Errors loading {table}: {errors[:2]}")
    else:
        print(f"  Loaded {len(rows):,} rows → {table}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", type=int, default=1000, help="Number of orders to generate")
    args = parser.parse_args()

    print(f"\nSeeding ecommerce dataset — {args.orders:,} orders")
    print(f"Target: {PROJECT}.{DATASET}")
    print(f"Mode: {'emulator (' + EMULATOR + ')' if EMULATOR else 'GCP BigQuery'}\n")

    client = get_client()

    print("Creating dataset and tables...")
    create_dataset(client)
    create_tables(client)

    print(f"\nGenerating data...")
    orders, order_items, sessions = generate_data(args.orders)
    print(f"  {len(orders):,} orders")
    print(f"  {len(order_items):,} order items")
    print(f"  {len(sessions):,} sessions")

    print("\nLoading into BigQuery...")
    load(client, "orders", orders)
    load(client, "order_items", order_items)
    load(client, "sessions", sessions)

    print("\nDone.")


if __name__ == "__main__":
    main()
