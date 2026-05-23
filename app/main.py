import asyncio
import logging
import os
import sentry_sdk
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import models  # noqa: F401
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.env_loader import load_and_validate_env
from app.core.redis_client import redis_client
from app.db.base import Base
from app.db.session import engine
from app.db.db_init import verify_database_connection

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(application: FastAPI):
    # 1. Load and validate environment variables (Module 10 Prod)
    load_and_validate_env()
    
    # 2. Configure logging
    configure_logging()
    
    settings = get_settings()

    # Delay heavier runtime imports until startup so the dashboard can boot faster.
    from app.jobs.scheduler import scheduler
    from app.jobs.tasks import slie_message_scanning
    from app.jobs.worker import follow_up_worker
    from app.services.response_engine import response_engine
    
    # 3. Initialize Sentry (Module 10 Prod)
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
        )
        logger.info("Sentry monitoring initialized.")

    # 4. Verify Database availability (Module 10 Prod) - deferred to background to avoid blocking
    async def verify_db_bg():
        try:
            await verify_database_connection()
        except Exception as e:
            logger.warning(f"Database verification in background failed: {e}. App will run with limited functionality.")
    
    # Schedule as background task
    asyncio.create_task(verify_db_bg())
    
    # 5. Initialize Redis (Module 10 Prod) - deferred to background
    async def init_redis_bg():
        try:
            await redis_client.connect()
            logger.info("Redis initialized in background.")
        except Exception as e:
            logger.warning(f"Redis initialization failed: {e}. Will use in-memory mock.")
    
    asyncio.create_task(init_redis_bg())
    
    # 6. Database schema creation (conditional) - deferred to background
    async def create_db_schema_bg():
        if settings.auto_create_tables:
            try:
                Base.metadata.create_all(bind=engine)
                logger.info("Database tables created automatically.")
            except Exception as e:
                logger.warning(f"Failed to create database tables: {e}")
    
    asyncio.create_task(create_db_schema_bg())
        
    # 6.5 Initialize Telegram Clients (Core & Elite) - deferred to background to avoid blocking startup
    async def init_telegram_clients():
        try:
            from slie.telegram.telegram_client import telegram_engine
            from app.services.telegram_client import telegram_client_manager
            
            # Connect SLIE Core Engine
            await telegram_engine.connect()
            
            # Connect Elite Manager (Primary Account)
            if settings.telegram_session_string:
                await telegram_client_manager.get_client()
                logger.info("Elite Telegram Client initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize Telegram clients: {e}")
    
    # Schedule as background task to avoid blocking FastAPI startup
    asyncio.create_task(init_telegram_clients())

    # 6.6 Initialize Power Upgrades Personas (deferred to background)
    async def init_personas():
        try:
            from app.services.power_upgrades import power_upgrades_service
            await power_upgrades_service.ensure_personas_initialized()
            logger.info("Power Upgrades personas initialized.")
        except Exception as e:
            logger.warning(f"Failed to initialize personas: {e}")
    
    asyncio.create_task(init_personas())

    # 7. Start schedulers and background tasks
    if settings.scheduler_enabled:
        scheduler.start()
        # Start message scanning in background
        asyncio.create_task(slie_message_scanning())
        # Start Human Behavior Simulation Engine background tasks (Module 3)
        asyncio.create_task(response_engine.manage_active_hours())
        
        # Start Follow-Up Worker (Module 9 Support)
        if settings.background_workers_enabled:
            asyncio.create_task(follow_up_worker.start())
            logger.info("Follow-Up Worker background task started.")
        
        logger.info("SLIE Background Schedulers and Scrapers started.")
    else:
        logger.info("Background schedulers are disabled (SCHEDULER_ENABLED=false).")
        
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
    # Serve local static dashboard assets at /dashboard
    application.mount("/dashboard", StaticFiles(directory="app/static/dashboard", html=True), name="dashboard")
    application.include_router(api_router, prefix="/api/v1")

    @application.get("/", include_in_schema=False)
    async def root_redirect():
        # Use the richer command dashboard as the primary landing page.
        return RedirectResponse(url="/api/v1/dashboard/overview")

    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

