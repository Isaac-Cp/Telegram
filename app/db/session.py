import ssl
from collections.abc import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings, normalize_database_url

settings = get_settings()
sanitized_async_db_url = normalize_database_url(settings.sqlalchemy_database_url)

# Sync engine (for existing code)
sync_db_url = sanitized_async_db_url.replace("postgresql+asyncpg", "postgresql+psycopg")
sync_db_url = sync_db_url.replace("ssl=true", "sslmode=require")

# PostgreSQL production defaults with pooling for sync engine
engine_args = {
    "pool_pre_ping": True,
    "pool_size": 20,
    "max_overflow": 100,
    "pool_timeout": 120,
    "pool_recycle": 1800,
    "connect_args": {"connect_timeout": 10},
}

engine = create_engine(sync_db_url, **engine_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)

# Async engine (for new asyncpg-based code)
async_engine_args = {
    "pool_pre_ping": True,
    "pool_size": 20,
    "max_overflow": 100,
    "pool_timeout": 120,
    "pool_recycle": 1800,
    "connect_args": {"timeout": 10, "command_timeout": 30},
}
db_url_lower = sanitized_async_db_url.lower() if sanitized_async_db_url else ""
# Only enable SSL for async engine when explicitly requested in the URL or when using known cloud hosts
if "postgresql" in db_url_lower and ("ssl=" in db_url_lower or "sslmode=" in db_url_lower or "neon" in db_url_lower):
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    async_engine_args["connect_args"]["ssl"] = ssl_context

async_engine = create_async_engine(sanitized_async_db_url, **async_engine_args)
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

