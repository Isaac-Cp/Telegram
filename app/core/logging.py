import logging
import sys
import traceback
import json
from datetime import datetime
from app.core.config import get_settings

def configure_logging() -> None:
    settings = get_settings()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("slie_production.log", encoding="utf-8")
        ],
        force=True
    )

    # Suppress verbose logging from external libraries that spam connection attempts
    # Telethon is particularly chatty with port scanning and connection attempts
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("telethon.network").setLevel(logging.ERROR)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("aioredis").setLevel(logging.WARNING)

    # Add custom structured loggers for specific modules (Module 10 structured logging)
    logger = logging.getLogger("SLIE")
    logger.info("SLIE Structured Logging initialized.")

def log_error(logger: logging.Logger, error: Exception, context: str = None, request_data: dict = None, response_data: dict = None):
    """
    Module 10: Comprehensive Structured Error Logging
    Captures timestamp, context, stack trace, and optional request/response data.
    """
    error_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "context": context,
        "error_type": type(error).__name__,
        "error_message": str(error),
        "stack_trace": traceback.format_exc(),
        "request_data": request_data,
        "response_data": response_data
    }

    logger.error(f"STRUCTURED_ERROR: {json.dumps(error_data, indent=2)}")


