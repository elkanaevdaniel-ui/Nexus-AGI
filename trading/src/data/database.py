"""Async SQLAlchemy engine and session management."""

from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.data.models import Base


async def create_engine(database_url: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine."""
    connect_args = {}
    if "sqlite" in database_url:
        connect_args["check_same_thread"] = False

    engine = create_async_engine(
        database_url,
        echo=False,
        connect_args=connect_args,
        pool_pre_ping=True,
    )
    return engine


async def create_tables(engine: AsyncEngine) -> None:
    """Create all tables (dev only — use Alembic in prod)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory."""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async session, rolling back on error."""
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
