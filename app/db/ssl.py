import ssl
from pathlib import Path

import certifi

from app.core.config import Settings


def build_verified_ssl_context(settings: Settings) -> ssl.SSLContext:
    cafile = settings.database_ssl_root_cert.strip() or certifi.where()
    return ssl.create_default_context(cafile=cafile)


def get_sync_ssl_root_cert(settings: Settings) -> str:
    return str(Path(settings.database_ssl_root_cert.strip() or certifi.where()))
