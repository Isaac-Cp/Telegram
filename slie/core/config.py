from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Streamexpert Lead Intelligence Engine"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = Field("postgresql+asyncpg://postgres:postgres@localhost:5432/slie_db", alias="DATABASE_URL")
    redis_url: str = Field("redis://localhost:6379/0", alias="REDIS_URL")
    sentry_dsn: str | None = Field(None, alias="SENTRY_DSN")

    @field_validator("database_url", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str) -> str:
        """Production fix: transform postgres:// or postgresql:// to postgresql+asyncpg:// if needed."""
        if not v or not isinstance(v, str):
            return v
            
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql://") and "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
            
        # Critical Render Fix: If hostname is 'postgres', it's likely a docker-compose carryover
        if "@postgres:" in v or "@postgres/" in v:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("[SLIE Config] DATABASE_URL is using 'postgres' as host. This will fail on Render.")
            
        return v
    
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
    business_hours_start: int = 9
    business_hours_end: int = 18


@lru_cache
def get_settings() -> Settings:
    return Settings()

