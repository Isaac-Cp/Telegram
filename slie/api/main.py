import asyncio
import logging
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI
from telethon import events
from slie.core.config import get_settings
from slie.core.database import engine, Base, AsyncSessionLocal
from slie.models.group_models import Group
from slie.models.lead_models import Lead, User
from slie.models.conversation_models import Message
from slie.telegram.telegram_client import telegram_engine
from slie.discovery.group_discovery import discovery_engine
from slie.discovery.group_analyzer import group_analyzer
from slie.intelligence.message_intelligence import message_intelligence
from slie.market_engine.seller_density_detector import seller_detector
from slie.engagement.human_behavior_engine import human_engine
from slie.engagement.conversation_strategy import conversation_strategy
from sqlalchemy import select

# Configure logging for production readiness
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("slie_runtime.log"),
    ],
)
logger = logging.getLogger(__name__)


async def slie_background_orchestrator():
    """
    Main background loop for discovery and market analysis.
    """
    logger.info("[SLIE Orchestrator] Starting background engine...")
    while True:
        try:
            # 1. Discover new groups
            await discovery_engine.discover_groups()

            # 2. Process discovered groups
            async with AsyncSessionLocal() as db:
                stmt = (
                    select(Group).where(Group.status == "DISCOVERED").limit(5)
                )
                result = await db.execute(stmt)
                groups = result.scalars().all()

                for group in groups:
                    logger.info(
                        f"[SLIE Orchestrator] Analyzing group: {group.name} ({group.telegram_id})"
                    )
                    # Step 5: Quality Filter
                    is_valid = await group_analyzer.analyze_group(
                        group.telegram_id
                    )

                    if is_valid and await human_engine.authorize_action(
                        "group_join"
                    ):
                        # Simulation: Since we are in a sandbox, we might not want to join real groups
                        # unless invite link is available. For MVP test, let's assume we can.
                        # await telegram_engine.join_group(...)
                        # For now, mark as JOINED to simulate activity
                        group.status = "JOINED"
                        logger.info(
                            f"[SLIE Orchestrator] Joined group: {group.name}"
                        )

                        # Step 6: Seller Density Check
                        await seller_detector.analyze_market_saturation(
                            group.telegram_id
                        )

                await db.commit()

            logger.info(
                "[SLIE Orchestrator] Cycle complete. Sleeping for 30 min."
            )
            await asyncio.sleep(1800)
        except Exception as e:
            logger.error(f"[SLIE Orchestrator] Error in cycle: {str(e)}")
            await asyncio.sleep(60)


async def lead_engagement_orchestrator():
    """
    Periodically check for new leads and trigger engagement strategy.
    """
    logger.info("[SLIE Lead Orchestrator] Starting engagement engine...")
    while True:
        try:
            async with AsyncSessionLocal() as db:
                # Find high probability leads that haven't been engaged yet
                # (For simplicity, we check leads from the last 10 minutes)
                ten_min_ago = datetime.utcnow() - timedelta(minutes=10)
                stmt = (
                    select(
                        Lead,
                        User.telegram_user_id,
                        Message.telegram_message_id,
                        Message.telegram_group_id,
                    )
                    .join(User, Lead.user_id == User.id)
                    .join(
                        Message,
                        (Message.telegram_user_id == User.telegram_user_id)
                        & (Message.body == Lead.message_text),
                    )
                    .where(
                        Lead.opportunity_score >= 70,
                        Lead.created_at >= ten_min_ago,
                    )
                )

                result = await db.execute(stmt)
                leads = result.all()

                for (
                    lead,
                    telegram_user_id,
                    telegram_message_id,
                    telegram_group_id,
                ) in leads:
                    logger.info(
                        f"[SLIE Lead Orchestrator] Engaging lead: {lead.id} (@{telegram_user_id})"
                    )
                    # Trigger engagement strategy in a separate task to not block the orchestrator
                    engagement_task = asyncio.create_task(
                        conversation_strategy.execute_strategy(
                            lead_id=lead.id,
                            user_id=telegram_user_id,
                            group_id=telegram_group_id,
                            message_id=telegram_message_id,
                            context=lead.message_text,
                        )
                    )
                    engagement_task.add_done_callback(
                        lambda task: logger.debug(
                            "Lead engagement task complete: %s",
                            task.exception() if task.exception() else "ok",
                        )
                    )

            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            logger.error(f"[SLIE Lead Orchestrator] Error: {str(e)}")
            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup
    settings = get_settings()
    logger.info(
        f"Starting {settings.app_name} in {settings.environment} mode..."
    )

    # Auto-create tables if enabled (Production MVP fix)
    if settings.auto_create_tables:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("[SLIE Database] Tables initialized successfully.")

    # Initialize Telegram Client (Step 3)
    if settings.telegram_session_string:
        client = await telegram_engine.connect()
        if client:
            # Register Message Intelligence (Step 7)
            telegram_engine.add_event_handler(
                message_intelligence.process_message,
                events.NewMessage(incoming=True),
            )
            # Start background orchestrator
            orchestrator_task = asyncio.create_task(
                slie_background_orchestrator()
            )
            orchestrator_task.add_done_callback(
                lambda task: logger.debug(
                    "Background orchestrator task complete: %s",
                    task.exception() if task.exception() else "ok",
                )
            )
            # Start lead engagement orchestrator
            engagement_task = asyncio.create_task(
                lead_engagement_orchestrator()
            )
            engagement_task.add_done_callback(
                lambda task: logger.debug(
                    "Lead engagement orchestrator task complete: %s",
                    task.exception() if task.exception() else "ok",
                )
            )

    yield

    # Shutdown
    await telegram_engine.disconnect()
    logger.info(f"{settings.app_name} shutdown complete.")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name, lifespan=lifespan, version="1.0.0-MVP"
    )

    @app.get("/")
    async def root():
        return {"message": "SLIE Intelligence System API is running."}

    @app.get("/health")
    async def health_check():
        """Render health check endpoint."""
        return {"status": "healthy", "engine": "SLIE Elite"}

    @app.post("/api/v1/discovery/trigger")
    async def trigger_discovery():
        """Manual trigger for group discovery."""
        discovery_task = asyncio.create_task(
            discovery_engine.discover_groups()
        )
        discovery_task.add_done_callback(
            lambda task: logger.debug(
                "Discovery task complete: %s",
                task.exception() if task.exception() else "ok",
            )
        )
        return {"status": "Discovery task initiated."}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
