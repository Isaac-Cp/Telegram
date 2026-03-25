import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from slie.core.config import get_settings, Settings
from slie.analytics.dashboard_service import dashboard_service
from slie.telegram.telegram_client import telegram_engine

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    logger.info(f"Starting {settings.app_name}...")
    
    # Initialize Telegram Client (Step 3)
    # Note: In a real production app, we'd handle session strings securely
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
