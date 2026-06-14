import asyncio
import inspect
import logging
import os
import sentry_sdk
import time
from contextlib import asynccontextmanager
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.env_loader import load_and_validate_env
from app.core.redis_client import redis_client
from app.core.rate_limit import get_limiter
from app.db.db_init import verify_database_connection

logger = logging.getLogger(__name__)

RATE_LIMIT_WINDOW = 60  # seconds


def validate_production_settings() -> None:
    settings = get_settings()
    production_issues = settings.production_issues()
    if production_issues:
        raise RuntimeError("Production configuration is not safe: " + " ".join(production_issues))


async def track_rate_limit_metrics(_: Request):
    window = int(time.time()) // RATE_LIMIT_WINDOW
    key = f"rate_limit:metrics:{window}"
    try:
        r = redis_client.client
        count = await r.incr(key)
        await r.expire(key, RATE_LIMIT_WINDOW)
        logger.debug("Rate limit metrics count: %s=%s", key, count)
    except Exception as e:
        logger.debug("Rate limit metrics tracking failed: %s", e)


from app.api.routes import health as health_routes

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
            health_routes.SYSTEM_HEALTH["degraded"].append(label)
            logger.critical(f"Escalating critical failure in {label}. Application state is now DEGRADED.")

@asynccontextmanager
async def lifespan(_: FastAPI):
    # 1. Load and validate environment variables (Module 10 Prod)
    load_and_validate_env()
    
    # 2. Configure logging
    configure_logging()
    
    validate_production_settings()
    settings = get_settings()

    async def startup_logic():
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
        if os.getenv("DEVELOPMENT", "").lower() != "true":
            try:
                import subprocess
                import sys
                subprocess.run([
                    sys.executable, "-m", "alembic", "upgrade", "head"
                ], capture_output=True, text=True, check=True, timeout=10)
                logger.info("Alembic migrations applied successfully.")
            except Exception as e:
                logger.warning(f"Alembic migrations could not be applied or timed out: {e}")

        # 5. Verify Database availability (Non-blocking spawn)
        asyncio.create_task(spawn_bg_task("Database Initialization", verify_database_connection, max_retries=1, escalate=False))

        # 6. Initialize Redis (Non-blocking spawn)
        asyncio.create_task(spawn_bg_task("Redis Initialization", redis_client.connect, max_retries=1, escalate=False))

        async def dashboard_cache_prewarm_bg():
            await redis_client.connect()
            from app.services.dashboard import prewarm_dashboard_cache
            await prewarm_dashboard_cache()

        asyncio.create_task(spawn_bg_task("Dashboard Cache Prewarm", dashboard_cache_prewarm_bg, max_retries=3, escalate=False))

        async def telegram_clients_bg():
            from app.services.telegram_client import telegram_client_manager
            if settings.telegram_enabled and settings.telegram_session_string:
                try:
                    await telegram_client_manager.get_client()
                    logger.info("Elite Telegram Client initialized.")
                except Exception as e:
                    logger.error(f"Telegram Client Initialization failed: {e}")
            elif not settings.telegram_enabled:
                logger.info("Telegram client initialization skipped (TELEGRAM_ENABLED=false).")

        asyncio.create_task(spawn_bg_task("Telegram Clients Initialization", telegram_clients_bg, max_retries=5, escalate=False))

        async def personas_bg():
            from app.services.power_upgrades import power_upgrades_service
            await power_upgrades_service.ensure_personas_initialized()
            logger.info("Power Upgrades personas initialized.")

        asyncio.create_task(spawn_bg_task("Personas Initialization", personas_bg, max_retries=5, escalate=True))

        # 7. Start schedulers and background tasks
        if settings.scheduler_enabled and os.getenv("DEVELOPMENT", "").lower() != "true":
            scheduler.start()
            if settings.telegram_enabled:
                asyncio.create_task(spawn_bg_task("Message Scanning", slie_message_scanning, max_retries=5, escalate=False))
                asyncio.create_task(spawn_bg_task("Response Engine Active Hours", response_engine.manage_active_hours, max_retries=5, escalate=False))
                from app.services.proxy_manager import proxy_manager
                asyncio.create_task(spawn_bg_task("Proxy Validation", proxy_manager.run_background_validation, max_retries=5, escalate=False))
            else:
                logger.info("Telegram background tasks skipped (TELEGRAM_ENABLED=false).")
            if settings.background_workers_enabled:
                asyncio.create_task(spawn_bg_task("Follow-Up Worker", follow_up_worker.start, max_retries=5, escalate=False))
                logger.info("Follow-Up Worker background task started.")
            logger.info("SLIE Background Schedulers and Scrapers started.")
        elif os.getenv("DEVELOPMENT", "").lower() == "true":
            logger.info("Background schedulers and tasks skipped in Development Mode.")
        else:
            logger.info("Background schedulers are disabled (SCHEDULER_ENABLED=false).")

    # Start all startup logic in a non-blocking way
    asyncio.create_task(startup_logic())
    
    yield
    
    # Shutdown flow
    try:
        from app.jobs.scheduler import scheduler
        if settings.scheduler_enabled and scheduler.running:
            scheduler.shutdown(wait=False)
    except Exception:
        pass
    
    await redis_client.disconnect()
    logger.info("SLIE Application shutdown complete.")


def create_app() -> FastAPI:
    validate_production_settings()
    settings = get_settings()
    application = FastAPI(
        title="SLIE API",
        description="Structured Lead Intelligence Engine for Telegram",
        version="1.5.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # 1. Security Headers Middleware (Module 16 Remediation)
    @application.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        connect_src = "'self' https://cdn.jsdelivr.net"
        if settings.environment != "production":
            connect_src = f"{connect_src} http://localhost:8000 http://127.0.0.1:8000"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://cdn.jsdelivr.net; "
            f"connect-src {connect_src}; "
            "worker-src 'self' blob:;"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # 2. CORS Middleware
    allowed_origins = ["*"] if settings.environment != "production" else settings.trusted_origins_list
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 3. Trusted Host Middleware
    allowed_hosts = settings.trusted_hosts_list if settings.environment == "production" else ["*"]
        
    application.add_middleware(
        TrustedHostMiddleware, 
        allowed_hosts=allowed_hosts
    )

    # 4. GZip Compression
    application.add_middleware(GZipMiddleware, minimum_size=1000)

    # 5. Rate Limiting Middleware
    limiter = get_limiter()
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    application.add_middleware(SlowAPIMiddleware)

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

    @application.get("/health", include_in_schema=False)
    async def simple_healthcheck():
        # Simple healthcheck for Render that doesn't require DB/Redis
        return {"status": "ok"}

    @application.get("/", include_in_schema=False)
    async def root_redirect():
        # Use the richer command dashboard as the primary landing page.
        return RedirectResponse(url="/api/v1/dashboard/overview")

    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
