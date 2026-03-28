from collections.abc import Generator, AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# Sync engine (for existing code)
sync_db_url = settings.sqlalchemy_database_url.replace("postgresql+asyncpg", "postgresql+psycopg").replace("sqlite+aiosqlite", "sqlite")

# Connection Pool Optimization (Fixes: QueuePool limit of size x overflow y reached)
# For SQLite, we switch to NullPool to disable pooling entirely, 
# which prevents QueuePool overflow errors in serverless/high-concurrency environments.
if "sqlite" in sync_db_url:
    from sqlalchemy.pool import NullPool
    engine_args = {
        "poolclass": NullPool,
    }
else:
    # PostgreSQL production defaults with pooling
    engine_args = {
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
    }

engine = create_engine(sync_db_url, **engine_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)

# Async engine (for new asyncpg-based code)
if "sqlite" in settings.sqlalchemy_database_url:
    from sqlalchemy.pool import NullPool
    async_engine_args = {
        "poolclass": NullPool,
    }
else:
    async_engine_args = {
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_timeout": 30,
    }

async_engine = create_async_engine(settings.sqlalchemy_database_url, **async_engine_args)
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False, class_=AsyncSession)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as db:
        try:
            yield db
        finally:
            await db.close()

