from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_api_key: str
    google_genai_api_key: str
    bigquery_dataset: str = "analytics"
    model_planner: str = "gemini-2.5-pro"
    model_executor: str = "gemini-2.5-flash"
    model_critic: str = "gemini-2.5-pro"
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    database_url: str = "postgresql+asyncpg://adk:adk@localhost:5432/adk_sessions"

    class Config:
        env_file = ".env"


settings = Settings()
