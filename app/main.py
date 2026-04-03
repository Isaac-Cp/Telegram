import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import logging
import sentry_sdk
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse

from app import models  # noqa: F401
from app.api.router import api_router
from app.core.config import get_settings
from app.core.health_checks import get_readiness_report
from app.core.logging import configure_logging
from app.core.migrations import run_database_migrations
from app.core.env_loader import load_and_validate_env
from app.core.redis_client import redis_client
from app.db.base import Base
from app.db.session import engine
from app.db.db_init import verify_database_connection

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(application: FastAPI):
    scheduler_instance = None
    try:
        # 1. Configure logging and validate environment
        configure_logging()
        load_and_validate_env()
        get_settings.cache_clear()
        
        settings = get_settings()
        logger.info(f"[SLIE Startup] Initializing {settings.app_name} v{settings.version} in {settings.environment} mode")
        logger.info(f"[SLIE Startup] Database URL: {settings.sqlalchemy_database_url.split('@')[-1] if '@' in settings.sqlalchemy_database_url else 'SQLite'}")
        
        # 3. Initialize Sentry (Module 10 Prod)
        if settings.sentry_dsn:
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment=settings.environment,
                traces_sample_rate=settings.sentry_traces_sample_rate,
                profiles_sample_rate=settings.sentry_profiles_sample_rate,
            )
            logger.info("Sentry monitoring initialized.")

        # 4. Run migrations before startup validation when explicitly enabled
        if settings.run_migrations_on_startup:
            await asyncio.to_thread(run_database_migrations)

        # 5. Verify Database availability (Module 10 Prod)
        await verify_database_connection()
        
        # 6. Initialize Redis only when this service depends on it
        await redis_client.connect()
        
        # 7. Database schema creation (conditional)
        if settings.auto_create_tables:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created automatically.")
            
        # 7.5 Initialize Telegram clients only when explicitly enabled
        if settings.telegram_enabled:
            try:
                from slie.telegram.telegram_client import telegram_engine
                from app.services.telegram_client import telegram_client_manager

                await telegram_engine.connect()

                if settings.telegram_session_string:
                    await telegram_client_manager.get_client()
                    logger.info("Elite Telegram client initialized.")
            except Exception as exc:
                logger.exception("Failed to initialize Telegram clients: %s", exc)
        else:
            logger.info("Telegram integrations are disabled.")

        # 7. Start optional background workers
        if settings.background_workers_enabled and settings.scheduler_enabled:
            try:
                from app.jobs.scheduler import scheduler
                from app.jobs.tasks import slie_message_scanning
                from app.services.response_engine import response_engine

                scheduler_instance = scheduler
                scheduler_instance.start()

                if settings.telegram_enabled:
                    asyncio.create_task(slie_message_scanning())
                    asyncio.create_task(response_engine.manage_active_hours())

                logger.info("SLIE background workers started.")
            except Exception as exc:
                logger.exception("Failed to start background workers: %s", exc)
        else:
            logger.info("Background workers are disabled.")
            
        yield
        
        # Shutdown flow
        if scheduler_instance is not None and scheduler_instance.running:
            scheduler_instance.shutdown(wait=False)
        await redis_client.disconnect()
        logger.info("SLIE Application shutdown complete.")
    except Exception as fatal_exc:
        import traceback
        print(f"FATAL STARTUP EXCEPTION: {fatal_exc}")
        traceback.print_exc()
        raise



def create_app() -> FastAPI:
    settings = get_settings()
    logger.info(f"Initializing {settings.app_name} v{settings.version} in {settings.environment} mode")
    application = FastAPI(
        title=settings.app_name, 
        lifespan=lifespan,
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None if settings.environment == "production" else "/redoc"
    )
    application.include_router(api_router, prefix="/api/v1")

    @application.get("/health", tags=["system"])
    async def health_check():
        """
        Elite Module 10: System Health & Versioning.
        Used to prevent frontend-backend mismatches during deployments.
        """
        settings = get_settings()
        return {
            "status": "healthy",
            "version": settings.version,
            "environment": settings.environment,
            "app_name": settings.app_name
        }

    @application.get("/ready", tags=["system"])
    async def readiness_check():
        payload, status_code = await get_readiness_report()
        return JSONResponse(status_code=status_code, content=payload)

    @application.get("/", include_in_schema=False)
    async def root_redirect():
        return RedirectResponse(url="/api/v1/dashboard/")

    return application


app = create_app()
