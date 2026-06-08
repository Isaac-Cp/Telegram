import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import get_settings, normalize_database_url
from app.db.ssl import build_verified_ssl_context

logger = logging.getLogger(__name__)

REQUIRED_TABLES = [
    "users",
    "groups",
    "leads",
    "lead_opportunities",
    "unified_conversations",
    "lead_value_scores",
    "dashboard_settings",
]

async def verify_database_connection():
    """
    Connect to PostgreSQL, verify availability, and check for required tables.
    In development mode (DEVELOPMENT=true), fails gracefully without blocking startup.
    """
    import os
    settings = get_settings()
    db_url = normalize_database_url(settings.sqlalchemy_database_url)
    
    # Development mode: skip blocking DB checks
    if os.getenv("DEVELOPMENT", "").lower() == "true":
        logger.info("SLIE DB Initialization: Development mode enabled. Skipping blocking database checks.")
        return True
    
    # Use PostgreSQL engine args; enable SSL only when requested in the URL
    engine_args = {"connect_args": {"timeout": 10, "command_timeout": 30}}
    db_url_lower = db_url.lower() if db_url else ""
    # Enable SSL when the URL explicitly contains ssl-related parameters or points to a cloud provider
    if "postgresql" in db_url_lower and ("ssl=" in db_url_lower or "sslmode=" in db_url_lower or "neon" in db_url_lower):
        engine_args["connect_args"]["ssl"] = build_verified_ssl_context(settings)

    engine = create_async_engine(db_url, **engine_args)
    
    max_retries = 3  # Reduced retries for faster failure
    retry_delay = 5  # Shorter delay for development
    
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.connect() as conn:
                # 1. Verify availability
                await conn.execute(text("SELECT 1"))
                logger.info("SLIE DB Initialization: Database connected successfully.")
                
                # 2. Check for required tables (Step 4 DB Audit)
                # Use information_schema for Postgres to list existing tables
                query = text(
                    """
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                    """
                )
                result = await conn.execute(query)
                existing_tables = {row[0] for row in result.fetchall()}
                
                missing_tables = [table for table in REQUIRED_TABLES if table not in existing_tables]
                
                if missing_tables:
                    raise RuntimeError(
                        "SLIE DB Initialization: Missing required tables: "
                        f"{', '.join(missing_tables)}. Ensure migrations have run."
                    )
                logger.info("SLIE DB Initialization: All required tables verified.")
                
                await engine.dispose()
                return True
                
        except Exception as e:
            logger.error(f"SLIE DB Initialization: Attempt {attempt}/{max_retries} failed to connect to database: {e}")
            if attempt < max_retries:
                logger.info(f"Retrying connection in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.critical("SLIE DB Initialization: All retries exhausted and database is unavailable.")
                raise RuntimeError("SLIE DB Initialization failed after retries")

if __name__ == "__main__":
    # For manual testing
    asyncio.run(verify_database_connection())
