from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_api_key: str
    google_genai_api_key: str
    google_cloud_project: str = "local-project"
    bigquery_dataset: str = "analytics"
    bigquery_emulator_host: str = ""
    model_planner: str = "gemini-2.5-pro"
    model_executor: str = "gemini-2.5-flash"
    model_critic: str = "gemini-2.5-pro"
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    database_url: str = "postgresql+asyncpg://adk:adk@localhost:5432/adk_sessions"
    ask_timeout_seconds: int = 120
    bigquery_query_timeout_seconds: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
