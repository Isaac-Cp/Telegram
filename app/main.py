import asyncio
import logging
import sentry_sdk
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app import models  # noqa: F401
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.env_loader import load_and_validate_env
from app.core.redis_client import redis_client
from app.db.base import Base
from app.db.session import engine
from app.db.db_init import verify_database_connection
from app.jobs.scheduler import scheduler
from app.jobs.tasks import slie_message_scanning
from app.services.response_engine import response_engine

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(application: FastAPI):
    # 1. Load and validate environment variables (Module 10 Prod)
    load_and_validate_env()
    
    # 2. Configure logging
    configure_logging()
    
    settings = get_settings()
    
    # 3. Initialize Sentry (Module 10 Prod)
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
        )
        logger.info("Sentry monitoring initialized.")

    # 4. Verify Database availability (Module 10 Prod)
    await verify_database_connection()
    
    # 5. Initialize Redis (Module 10 Prod)
    await redis_client.connect()
    
    # 6. Database schema creation (conditional)
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created automatically.")
        
    # 7. Start schedulers and background tasks
    if settings.scheduler_enabled:
        scheduler.start()
        # Start message scanning in background
        asyncio.create_task(slie_message_scanning())
        # Start Human Behavior Simulation Engine background tasks (Module 3)
        asyncio.create_task(response_engine.manage_active_hours())
        logger.info("SLIE Background Schedulers and Scrapers started.")
        
    yield
    
    # Shutdown flow
    if settings.scheduler_enabled and scheduler.running:
        scheduler.shutdown(wait=False)
    await redis_client.disconnect()
    logger.info("SLIE Application shutdown complete.")


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name, 
        lifespan=lifespan,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None if settings.environment == "production" else "/redoc"
    )
    application.include_router(api_router)
    return application


app = create_app()

