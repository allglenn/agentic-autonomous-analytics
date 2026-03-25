from google.adk.sessions import DatabaseSessionService
from config.settings import settings

# Single shared session service backed by PostgreSQL.
# DatabaseSessionService uses SQLAlchemy async engine under the hood.
session_service = DatabaseSessionService(db_url=settings.database_url)
