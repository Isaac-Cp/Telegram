import re
import logging
from functools import lru_cache
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(value: str) -> str:
    """Normalize DATABASE_URL for SQLAlchemy asyncpg usage.

    Render/Neon URLs often arrive as `postgres://...?...sslmode=require`.
    We force the async driver and strip SSL query params so SSL is supplied
    through engine connect args instead of leaking unsupported kwargs to asyncpg.
    """
    if not value or not isinstance(value, str):
        return value

    if value.startswith("postgres://"):
        value = value.replace("postgres://", "postgresql://", 1)

    if value.startswith("postgresql://"):
        value = value.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif value.startswith("postgresql+") and "+asyncpg" not in value:
        value = re.sub(r"postgresql\+[^:]+://", "postgresql+asyncpg://", value)

    parsed = urlparse(value)
    query_params = parse_qs(parsed.query)
    for param in ("sslmode", "ssl", "sslcert", "sslkey", "sslrootcert"):
        query_params.pop(param, None)

    query = urlencode(query_params, doseq=True) if query_params else ""
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Streamexpert Lead Intelligence Engine"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = Field("postgresql+asyncpg://postgres:postgres@localhost:5432/slie_db", alias="DATABASE_URL")
    
    @field_validator("database_url", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str) -> str:
        """Normalize database URLs from Render/Neon/Heroku into asyncpg format."""
        v = normalize_database_url(v)

        # Critical Render Fix: If hostname is 'postgres', it's likely a docker-compose carryover
        if "@postgres:" in v or "@postgres/" in v:
            logger = logging.getLogger(__name__)
            logger.warning("[SLIE Config] DATABASE_URL is using 'postgres' as host. This will fail on Render.")
            
        return v

    @property
    def sqlalchemy_database_url(self) -> str:
        """Redundant but kept for compatibility with existing code calling this property."""
        return self.database_url

    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    sentry_dsn: str | None = Field(None, alias="SENTRY_DSN")
    
    # OpenAI, Groq, Gemini keys
    openai_api_key: str = Field("", alias="OPENAI_API_KEY")
    groq_api_key: str = Field("", alias="GROQ_API_KEY")
    gemini_api_key: str = Field("", alias="GEMINI_API_KEY")
    
    # Telegram Userbot Settings
    telegram_api_id: int = Field(0, alias="API_ID")
    telegram_api_hash: str = Field("", alias="API_HASH")
    telegram_phone: str = Field("", alias="PHONE_NUMBER")
    telegram_session_string: str | None = Field(None, alias="SESSION_STRING")
    telegram_session_name: str = "slie_session"
    
    # Proxy Settings (Module 2)
    telegram_proxy_host: str | None = Field(None, alias="TELEGRAM_PROXY_HOST")
    telegram_proxy_port: int | None = Field(None, alias="TELEGRAM_PROXY_PORT")
    telegram_proxy_type: str | None = Field(None, alias="TELEGRAM_PROXY_TYPE") # 'socks5', 'http'
    
    # Reddit Settings
    reddit_client_id: str = Field("", alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field("", alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = "slie-bot/0.1"
    
    # SLIE Limits
    max_groups_join_per_day: int = 2
    max_public_replies_per_day: int = 5
    max_dms_per_day: int = 2 # Updated for maximum safety as per user request
    public_reply_delay_minutes: int = 20
    dm_delay_min_minutes: int = 15
    dm_delay_max_minutes: int = 45
    
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    timezone: str = "Africa/Lagos"
    scheduler_enabled: bool = True
    auto_create_tables: bool = Field(False, alias="AUTO_CREATE_TABLES")
    default_follow_up_delay_minutes: int = 1440
    business_hours_start: int = Field(0, alias="BUSINESS_HOURS_START")
    business_hours_end: int = Field(23, alias="BUSINESS_HOURS_END")
    background_workers_enabled: bool = Field(True, alias="BACKGROUND_WORKERS_ENABLED")

    # Database cleanup retention settings
    cleanup_enabled: bool = Field(True, alias="CLEANUP_ENABLED")
    cleanup_batch_size: int = Field(1000, alias="CLEANUP_BATCH_SIZE")
    messages_retention_days: int = Field(90, alias="MESSAGES_RETENTION_DAYS")
    activity_events_retention_days: int = Field(90, alias="ACTIVITY_EVENTS_RETENTION_DAYS")
    unified_conversations_retention_days: int = Field(30, alias="UNIFIED_CONVERSATIONS_RETENTION_DAYS")
    follow_up_jobs_retention_days: int = Field(30, alias="FOLLOW_UP_JOBS_RETENTION_DAYS")
    group_join_history_retention_days: int = Field(90, alias="GROUP_JOIN_HISTORY_RETENTION_DAYS")
    metrics_snapshots_retention_days: int = Field(365, alias="METRICS_SNAPSHOTS_RETENTION_DAYS")
    lead_conversations_retention_days: int = Field(30, alias="LEAD_CONVERSATIONS_RETENTION_DAYS")

    # Email Settings
    smtp_host: str = Field("smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(587, alias="SMTP_PORT")
    smtp_user: str = Field("", alias="SMTP_USER")
    smtp_password: str = Field("", alias="SMTP_PASSWORD")
    emails_enabled: bool = Field(False, alias="EMAILS_ENABLED")
    admin_email: str = Field("", alias="ADMIN_EMAIL")


@lru_cache
def get_settings() -> Settings:
    return Settings()

