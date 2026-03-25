import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from slie.core.config import get_settings, Settings
from slie.core.database import engine, Base
from slie.analytics.dashboard_service import dashboard_service
from slie.telegram.telegram_client import telegram_engine

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    logger.info(f"Starting {settings.app_name} in {settings.environment} mode...")
    
    # Auto-create tables if enabled (Production MVP fix)
    if settings.auto_create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("[SLIE Database] Tables initialized successfully.")

    # Initialize Telegram Client (Step 3)
    if settings.telegram_session_string:
        await telegram_engine.connect()
    
    yield
    
    # Shutdown
    await telegram_engine.disconnect()
    logger.info(f"{settings.app_name} shutdown complete.")

def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        version="1.0.0-MVP"
    )

    @app.get("/")
    async def root():
        return {"message": "SLIE Intelligence System API is running."}

    @app.get("/health")
    async def health_check():
        """Render health check endpoint."""
        return {"status": "healthy", "engine": "SLIE Elite"}

    @app.get("/api/v1/stats")
    async def get_stats():
        """
        STEP 15: ANALYTICS ENGINE
        """
        return await dashboard_service.get_stats()

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
