from collections.abc import AsyncGenerator, Generator
from urllib.parse import quote

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings, normalize_database_url
from app.db.ssl import build_verified_ssl_context, get_sync_ssl_root_cert

settings = get_settings()
sanitized_async_db_url = normalize_database_url(settings.sqlalchemy_database_url)
db_url_lower = sanitized_async_db_url.lower() if sanitized_async_db_url else ""
requires_verified_ssl = "postgresql" in db_url_lower and (
    "ssl=" in db_url_lower or "sslmode=" in db_url_lower or "neon" in db_url_lower
)

# Sync engine (for existing code)
sync_db_url = sanitized_async_db_url.replace("postgresql+asyncpg", "postgresql+psycopg")
sync_db_url = sync_db_url.replace("ssl=true", "sslmode=require")
if requires_verified_ssl and "sslmode=" not in sync_db_url.lower():
    separator = "&" if "?" in sync_db_url else "?"
    root_cert = quote(get_sync_ssl_root_cert(settings), safe="")
    sync_db_url = f"{sync_db_url}{separator}sslmode=verify-full&sslrootcert={root_cert}"

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
# Only enable SSL for async engine when explicitly requested in the URL or when using known cloud hosts
if requires_verified_ssl:
    async_engine_args["connect_args"]["ssl"] = build_verified_ssl_context(settings)

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

