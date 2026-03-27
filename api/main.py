from dotenv import load_dotenv
load_dotenv()

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from api.routes import router
from config.settings import settings
from db.conversations import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(__name__)


async def _seed_bigquery_if_needed():
    """Seed the BigQuery emulator if the orders table is missing."""
    if not settings.bigquery_emulator_host:
        return
    try:
        from bigquery.client import get_client
        client = await asyncio.to_thread(get_client)
        tables = await asyncio.to_thread(lambda: list(client.list_tables("analytics")))
        table_ids = [t.table_id for t in tables]
        if "orders" not in table_ids:
            logger.info("BigQuery emulator has no data — running seed script")
            import subprocess, sys
            await asyncio.to_thread(
                lambda: subprocess.run(
                    [sys.executable, "scripts/seed_data.py"],
                    check=True,
                )
            )
            logger.info("BigQuery seed complete")
        else:
            logger.info("BigQuery emulator already has data — skipping seed")
    except Exception:
        logger.exception("BigQuery seed failed — queries may not work")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _seed_bigquery_if_needed()
    yield


app = FastAPI(
    title="AI Data Analyst",
    description="Agentic data analysis powered by Google ADK + BigQuery",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
