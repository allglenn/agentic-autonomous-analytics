"""
Self-managed conversation store.
Tracks conversations independently of ADK sessions.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config.settings import settings


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(200), nullable=False, default="New conversation")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


_engine = create_async_engine(settings.database_url, echo=False)
_Session = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def create_conversation(session_id: str, title: str) -> Conversation:
    async with _Session() as db:
        conv = Conversation(id=session_id, title=title[:200])
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return conv


async def get_conversations() -> list[Conversation]:
    async with _Session() as db:
        result = await db.execute(select(Conversation).order_by(Conversation.created_at.desc()))
        return result.scalars().all()


async def update_title(session_id: str, title: str) -> bool:
    async with _Session() as db:
        result = await db.execute(select(Conversation).where(Conversation.id == session_id))
        conv = result.scalar_one_or_none()
        if conv is None:
            return False
        conv.title = title[:200]
        conv.updated_at = datetime.now(timezone.utc)
        await db.commit()
        return True


async def delete_conversation(session_id: str) -> bool:
    async with _Session() as db:
        result = await db.execute(delete(Conversation).where(Conversation.id == session_id))
        await db.commit()
        return result.rowcount > 0
