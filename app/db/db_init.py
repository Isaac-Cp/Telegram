import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import get_settings

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
    Connect to PostgreSQL, verify availability, and check for required tables.
    """
    settings = get_settings()
    engine = create_async_engine(settings.sqlalchemy_database_url)
    
    max_retries = 10
    retry_delay = 30 # seconds
    
    for attempt in range(1, max_retries + 1):
        try:
            async with engine.connect() as conn:
                # 1. Verify availability
                await conn.execute(text("SELECT 1"))
                logger.info(f"SLIE DB Initialization: Database connected successfully to {settings.sqlalchemy_database_url}")
                
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
                    logger.warning(f"SLIE DB Initialization: Missing required tables: {', '.join(missing_tables)}. Ensure migrations have run.")
                else:
                    logger.info("SLIE DB Initialization: All required tables verified.")
                
                await engine.dispose()
                return True
                
        except Exception as e:
            logger.error(f"SLIE DB Initialization: Attempt {attempt}/{max_retries} failed to connect to database: {e}")
            if attempt < max_retries:
                logger.info(f"Retrying connection in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.critical("SLIE DB Initialization: Maximum connection attempts reached. Application cannot start.")
                raise ConnectionError("Database connection failed after multiple attempts.")
    
    return False

if __name__ == "__main__":
    # For manual testing
    configure_logging()
    asyncio.run(verify_database_connection())
