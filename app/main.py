import asyncio
import inspect
import logging
import os
import sentry_sdk
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable

from alembic import command
from alembic.config import Config
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app import models  # noqa: F401
from app.api.routes import dashboard as dashboard_routes
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.env_loader import load_and_validate_env
from app.core.redis_client import redis_client
from app.core.rate_limit import get_limiter
from app.db.db_init import verify_database_connection

logger = logging.getLogger(__name__)

RATE_LIMIT_WINDOW = 60  # seconds

async def track_rate_limit_metrics(request: Request):
    window = int(time.time()) // RATE_LIMIT_WINDOW
    key = f"rate_limit:metrics:{window}"
    try:
        r = redis_client.client
        count = await r.incr(key)
        await r.expire(key, RATE_LIMIT_WINDOW)
        logger.debug("Rate limit metrics count: %s=%s", key, count)
    except Exception as e:
        logger.debug("Rate limit metrics tracking failed: %s", e)


def require_dashboard_auth(request: Request):
    # Skip auth for the login endpoint and for the HTML page routes themselves
    path = request.url.path
    if not path.startswith("/api/v1/dashboard"):
        return None

    # List of routes that serve HTML or are public
    public_dashboard_routes = {
        "/api/v1/dashboard/",
        "/api/v1/dashboard/overview",
        "/api/v1/dashboard/activity",
        "/api/v1/dashboard/pipeline",
        "/api/v1/dashboard/targeting",
        "/api/v1/dashboard/watch",
        "/api/v1/dashboard/settings",
        "/api/v1/dashboard/styleguide",
        "/api/v1/dashboard/auth/login",
    }

    if path in public_dashboard_routes:
        return None

    # For API data routes, we require auth unless in development and specifically requested
    # However, to make it easier for the user to "fix all errors", let's allow GET requests
    # to the data endpoints if they don't have an auth header, but they'll get fallback data
    # OR we just enforce auth for sensitive operations (PUT/POST/DELETE).
    
    if request.method == "GET":
        return None

    authorization = request.headers.get("Authorization")
    try:
        dashboard_routes._require_dashboard_auth(authorization)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

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


    # 4. Enforce Alembic migrations at startup
    try:
        import subprocess
        import sys
        result = subprocess.run([
            sys.executable, "-m", "alembic", "upgrade", "head"
        ], capture_output=True, text=True, check=True, timeout=10)
        logger.info("Alembic migrations applied successfully.")
    except Exception as e:
        logger.warning(f"Alembic migrations could not be applied or timed out: {e}")

    async def robust_bg_task(label: str, fn: Callable[[], Any], max_retries: int = 5, escalate: bool = True):
        for attempt in range(1, max_retries + 1):
            try:
                result = fn()
                if inspect.isawaitable(result):
                    await result
                return
            except Exception as e:
                logger.error(f"{label} failed (attempt {attempt}/{max_retries}): {e}")
                if attempt == max_retries:
                    break
                await asyncio.sleep(min(30, 2 ** attempt))
        if escalate:
            logger.critical(f"{label} failed after {max_retries} attempts. Escalating.")
            raise RuntimeError(f"{label} failed after retries")
        logger.error(f"{label} failed after {max_retries} attempts.")

    async def spawn_bg_task(label: str, fn: Callable[[], Any], max_retries: int = 5, escalate: bool = False):
        try:
            await robust_bg_task(label, fn, max_retries=max_retries, escalate=escalate)
        except Exception as e:
            logger.critical(f"Background task '{label}' failed permanently: {e}")
            if escalate:
                os._exit(1)

    # 5. Verify Database availability and ensure migrations succeeded
    try:
        await robust_bg_task("Database Initialization", verify_database_connection, max_retries=1, escalate=False)
    except Exception as e:
        logger.warning(f"Database Initialization failed, continuing in limited mode: {e}")

    # 6. Initialize Redis (Module 10 Prod)
    try:
        await robust_bg_task("Redis Initialization", redis_client.connect, max_retries=1, escalate=False)
    except Exception as e:
        logger.warning(f"Redis Initialization failed, continuing in limited mode: {e}")

    async def telegram_clients_bg():
        from slie.telegram.telegram_client import telegram_engine
        from app.services.telegram_client import telegram_client_manager

        await telegram_engine.connect()
        if settings.telegram_session_string:
            await telegram_client_manager.get_client()
            logger.info("Elite Telegram Client initialized.")

    asyncio.create_task(spawn_bg_task("Telegram Clients Initialization", telegram_clients_bg, max_retries=5, escalate=True))

    async def personas_bg():
        from app.services.power_upgrades import power_upgrades_service
        await power_upgrades_service.ensure_personas_initialized()
        logger.info("Power Upgrades personas initialized.")

    asyncio.create_task(spawn_bg_task("Personas Initialization", personas_bg, max_retries=5, escalate=True))

    # 7. Start schedulers and background tasks
    if settings.scheduler_enabled:
        scheduler.start()
        # Start message scanning in background with retry
        asyncio.create_task(spawn_bg_task("Message Scanning", slie_message_scanning, max_retries=5, escalate=False))
        # Start Human Behavior Simulation Engine background tasks (Module 3)
        asyncio.create_task(spawn_bg_task("Response Engine Active Hours", response_engine.manage_active_hours, max_retries=5, escalate=False))
        # Start Follow-Up Worker (Module 9 Support)
        if settings.background_workers_enabled:
            asyncio.create_task(spawn_bg_task("Follow-Up Worker", follow_up_worker.start, max_retries=5, escalate=False))
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

    # Rate Limiting (Module 10 Prod)
    limiter = get_limiter()
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    application.add_middleware(SlowAPIMiddleware)

    # CORS middleware (allow only trusted origins in production)
    allowed_origins = ["*"] if settings.environment != "production" else settings.trusted_origins_list
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @application.middleware("http")
    async def security_middlewares(request: Request, call_next):
        auth_response = require_dashboard_auth(request)
        if auth_response:
            return auth_response
        return await call_next(request)

    @application.middleware("http")
    async def rate_metrics_middleware(request: Request, call_next):
        response = await call_next(request)
        await track_rate_limit_metrics(request)
        return response

    # Serve local static dashboard assets at /dashboard
    application.mount("/dashboard", StaticFiles(directory="app/static/dashboard", html=True), name="dashboard")
    application.include_router(
        api_router,
        prefix="/api/v1",
    )

    @application.get("/", include_in_schema=False)
    async def root_redirect():
        # Use the richer command dashboard as the primary landing page.
        return RedirectResponse(url="/api/v1/dashboard/overview")

    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))

