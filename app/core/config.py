import os
import re
import logging
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

def get_version() -> str:
    try:
        version_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "VERSION")
        with open(version_path, "r") as f:
            return f.read().strip()
    except Exception:
        return "1.0.0"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Streamexpert Lead Intelligence Engine"
    version: str = get_version()
    environment: str = Field("development", alias="ENVIRONMENT")
    port: int = Field(8000, alias="PORT")
    api_v1_prefix: str = "/api/v1"
    database_url: str = Field("postgresql+asyncpg://postgres:postgres@localhost:5432/slie_db", alias="DATABASE_URL")
    
    @field_validator("database_url", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str) -> str:
        """
        Validate and format the database URL for SQLAlchemy asyncpg.
        Ensures postgres:// is converted to postgresql+asyncpg:// for async compatibility.
        """
        if not v:
            return "sqlite+aiosqlite:///./test.db"
            
        # 1. Handle Render/Heroku legacy postgres:// prefix
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)
            
        # 2. Ensure asyncpg driver for postgresql://
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgresql+") and "+asyncpg" not in v:
            v = re.sub(r"postgresql\+[^:]+://", "postgresql+asyncpg://", v)
        elif v.startswith("sqlite:///"):
            v = v.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
            
        # 3. Add sslmode=require if on Render (detected by postgresql)
        if "postgresql" in v and "ssl=" not in v and "sslmode=" not in v:
            separator = "&" if "?" in v else "?"
            v = f"{v}{separator}ssl=require"
            
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
    max_groups_join_per_day: int = 50 # Increased for demonstration
    max_public_replies_per_day: int = 5
    max_dms_per_day: int = 2 # Updated for maximum safety as per user request
    public_reply_delay_minutes: int = 20
    dm_delay_min_minutes: int = 15
    dm_delay_max_minutes: int = 45
    
    # Safe join rate per hour (Module 3 Safety)
    max_groups_join_per_hour: int = 20 # Increased for demonstration
    
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    timezone: str = "Africa/Lagos"
    scheduler_enabled: bool = Field(True, alias="SCHEDULER_ENABLED")
    background_workers_enabled: bool = Field(False, alias="BACKGROUND_WORKERS_ENABLED")
    telegram_enabled: bool = Field(False, alias="TELEGRAM_ENABLED")
    low_cpu_mode: bool = Field(True, alias="LOW_CPU_MODE")
    redis_required: bool = Field(False, alias="REDIS_REQUIRED")
    auto_create_tables: bool = Field(False, alias="AUTO_CREATE_TABLES")
    run_migrations_on_startup: bool = Field(False, alias="RUN_MIGRATIONS_ON_STARTUP")
    database_connect_max_retries: int = Field(3, alias="DATABASE_CONNECT_MAX_RETRIES")
    database_connect_retry_delay_seconds: int = Field(5, alias="DATABASE_CONNECT_RETRY_DELAY_SECONDS")
    redis_connect_timeout_seconds: float = Field(2.0, alias="REDIS_CONNECT_TIMEOUT_SECONDS")
    max_message_analysis_concurrency: int = Field(2, alias="MAX_MESSAGE_ANALYSIS_CONCURRENCY")
    admin_cache_ttl_seconds: int = Field(21600, alias="ADMIN_CACHE_TTL_SECONDS")
    memory_summary_trigger_messages: int = Field(250, alias="MEMORY_SUMMARY_TRIGGER_MESSAGES")
    memory_summary_check_interval: int = Field(25, alias="MEMORY_SUMMARY_CHECK_INTERVAL")
    scheduler_public_reply_interval_minutes: int = Field(10, alias="SCHEDULER_PUBLIC_REPLY_INTERVAL_MINUTES")
    scheduler_private_dm_interval_minutes: int = Field(10, alias="SCHEDULER_PRIVATE_DM_INTERVAL_MINUTES")
    scheduler_reddit_interval_hours: int = Field(3, alias="SCHEDULER_REDDIT_INTERVAL_HOURS")
    scheduler_power_upgrades_interval_minutes: int = Field(120, alias="SCHEDULER_POWER_UPGRADES_INTERVAL_MINUTES")
    sentry_traces_sample_rate: float = Field(0.0, alias="SENTRY_TRACES_SAMPLE_RATE")
    sentry_profiles_sample_rate: float = Field(0.0, alias="SENTRY_PROFILES_SAMPLE_RATE")
    default_follow_up_delay_minutes: int = 1440
    business_hours_start: int = Field(0, alias="BUSINESS_HOURS_START")
    business_hours_end: int = Field(23, alias="BUSINESS_HOURS_END")


@lru_cache
def get_settings() -> Settings:
    return Settings()
