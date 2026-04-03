import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

REQUIRED_VARS = [
    "DATABASE_URL",
]

def load_and_validate_env():
    """
    Load environment variables from .env and validate required ones.
    """
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info("Loaded environment variables from .env")
    else:
        logger.warning(".env file not found. Relying on system environment variables.")

    missing = [var for var in REQUIRED_VARS if not os.getenv(var)]

    telegram_enabled = os.getenv("TELEGRAM_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}
    telegram_session_present = bool(os.getenv("SESSION_STRING"))

    if telegram_enabled or telegram_session_present:
        telegram_required = ["API_ID", "API_HASH", "SESSION_STRING"]
        missing.extend([var for var in telegram_required if not os.getenv(var)])
    
    if missing:
        error_msg = f"Critical Configuration Error: Missing required environment variables: {', '.join(missing)}"
        logger.error(error_msg)
        raise EnvironmentError(error_msg)
    
    logger.info("Environment variables validated successfully.")
