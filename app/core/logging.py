import logging
import sys
from app.core.config import get_settings

def configure_logging() -> None:
    settings = get_settings()
    
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("slie_production.log")
        ]
    )
    
    # Add custom structured loggers for specific modules (Module 10 structured logging)
    logger = logging.getLogger("SLIE")
    logger.info("SLIE Structured Logging initialized.")


