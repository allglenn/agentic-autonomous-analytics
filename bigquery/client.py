from functools import lru_cache
from google.cloud import bigquery
from config.settings import settings


@lru_cache(maxsize=1)
def get_client() -> bigquery.Client:
    """Return a singleton BigQuery client."""
    return bigquery.Client(project=settings.google_cloud_project)
