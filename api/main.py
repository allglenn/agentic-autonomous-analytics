from fastapi import FastAPI
from api.routes import router
from config.settings import settings

app = FastAPI(
    title="AI Data Analyst",
    description="Agentic data analysis powered by Google ADK + BigQuery",
    version="0.1.0",
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
