from typing import Dict

# dimension_name → source column
DIMENSIONS: Dict[str, str] = {
    "channel": "marketing_channel",
    "country": "shipping_country",
    "campaign": "utm_campaign",
    "device": "device_type",
    "product_category": "product_category",
}
