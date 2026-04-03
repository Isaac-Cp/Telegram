import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)

REQUIRED_TABLES = [
    "users",
    "groups",
    "leads",
    "lead_opportunities",
    "unified_conversations",
    "lead_value_scores"
]

async def verify_database_connection():
    """
    Connect to the configured database, verify availability, and check for required tables.
    """
    settings = get_settings()
    masked_db_url = _mask_database_url(settings.sqlalchemy_database_url)
    
    # Use NullPool for SQLite to avoid QueuePool overflow during verification
    engine_args = {}
    if settings.database_url.startswith("sqlite"):
        from sqlalchemy.pool import NullPool
        engine_args["poolclass"] = NullPool
    
    engine = create_async_engine(settings.sqlalchemy_database_url, **engine_args)
    
    max_retries = settings.database_connect_max_retries
    retry_delay = settings.database_connect_retry_delay_seconds
    
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.connect() as conn:
                # 1. Verify availability
                await conn.execute(text("SELECT 1"))
                logger.info("SLIE DB Initialization: Database connected successfully to %s", masked_db_url)
                
                # 2. Check for required tables (Step 4 DB Audit)
                if engine.url.drivername.startswith("sqlite"):
                    query = text("SELECT name FROM sqlite_master WHERE type='table'")
                else:
                    query = text("""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                    """)
                result = await conn.execute(query)
                existing_tables = {row[0] for row in result.fetchall()}
                
                missing_tables = [table for table in REQUIRED_TABLES if table not in existing_tables]
                
                if missing_tables:
                    logger.warning(
                        "SLIE DB Initialization: Missing required tables: %s. Ensure migrations have run.",
                        ", ".join(missing_tables),
                    )
                else:
                    logger.info("SLIE DB Initialization: All required tables verified.")
                
                await engine.dispose()
                return True
                
        except Exception as e:
            logger.error(
                "SLIE DB Initialization: Attempt %s/%s failed to connect to %s: %s",
                attempt,
                max_retries,
                masked_db_url,
                e,
            )
            if attempt < max_retries:
                logger.info("Retrying connection in %s seconds...", retry_delay)
                await asyncio.sleep(retry_delay)
            else:
                logger.critical("SLIE DB Initialization: Maximum connection attempts reached. Application cannot start.")
                raise ConnectionError("Database connection failed after multiple attempts.")
    
    return False

if __name__ == "__main__":
    # For manual testing
    configure_logging()
    asyncio.run(verify_database_connection())


def _mask_database_url(db_url: str) -> str:
    try:
        return make_url(db_url).render_as_string(hide_password=True)
    except Exception:
        return "<unparseable database url>"
