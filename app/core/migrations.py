import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)


def run_database_migrations() -> None:
    root_dir = Path(__file__).resolve().parents[2]
    config = Config(str(root_dir / "alembic.ini"))
    config.set_main_option("script_location", str(root_dir / "migrations"))
    config.set_main_option("prepend_sys_path", str(root_dir))
    command.upgrade(config, "head")
    logger.info("Database migrations applied successfully.")
