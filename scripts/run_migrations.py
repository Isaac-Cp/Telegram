import logging
from alembic.config import Config
from alembic import command

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

alembic_cfg = Config("alembic.ini")

if __name__ == '__main__':
    logger.info('Running Alembic upgrade head')
    command.upgrade(alembic_cfg, 'head')
    logger.info('Alembic upgrade complete')
