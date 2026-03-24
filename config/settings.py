from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_cloud_project: str
    google_application_credentials: str
    bigquery_dataset: str = "analytics"
    model_name: str = "gemini-2.5-pro"
    api_host: str = "0.0.0.0"
    api_port: int = 8080

    class Config:
        env_file = ".env"


settings = Settings()
