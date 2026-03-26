from functools import lru_cache
from google.cloud import bigquery
from google.api_core.client_options import ClientOptions
from config.settings import settings


@lru_cache(maxsize=1)
def get_client() -> bigquery.Client:
    """
    Return a singleton BigQuery client.
    If BIGQUERY_EMULATOR_HOST is set, points to the local emulator instead of GCP.
    """
    if settings.bigquery_emulator_host:
        client_options = ClientOptions(api_endpoint=f"http://{settings.bigquery_emulator_host}")
        return bigquery.Client(
            project=settings.google_cloud_project,
            client_options=client_options,
        )

    return bigquery.Client(project=settings.google_cloud_project)
