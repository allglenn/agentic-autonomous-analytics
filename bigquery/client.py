import os
from functools import lru_cache
from google.cloud import bigquery
from google.api_core.client_options import ClientOptions


@lru_cache(maxsize=1)
def get_client() -> bigquery.Client:
    """
    Return a singleton BigQuery client.
    If BIGQUERY_EMULATOR_HOST is set, points to the local emulator instead of GCP.
    """
    emulator_host = os.getenv("BIGQUERY_EMULATOR_HOST")
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "local-project")

    if emulator_host:
        client_options = ClientOptions(api_endpoint=f"http://{emulator_host}")
        return bigquery.Client(
            project=project,
            client_options=client_options,
        )

    return bigquery.Client(project=project)
