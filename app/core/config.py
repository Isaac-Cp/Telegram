import re
import logging
from functools import lru_cache
from pathlib import Path
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
    for param in ("sslmode", "ssl", "sslcert", "sslkey", "sslrootcert", "channel_binding"):
        query_params.pop(param, None)

    query = urlencode(query_params, doseq=True) if query_params else ""
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, query, parsed.fragment))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "Streamexpert Lead Intelligence Engine"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = Field("postgresql+asyncpg://postgres:postgres@localhost:5432/slie_db", alias="DATABASE_URL")
    database_ssl_root_cert: str = Field("", alias="DATABASE_SSL_ROOT_CERT")
    
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
    telegram_enabled: bool = Field(True, alias="TELEGRAM_ENABLED")
    
    # Proxy Settings (Module 2)
    telegram_proxy_host: str | None = Field(None, alias="TELEGRAM_PROXY_HOST")
    telegram_proxy_port: int | None = Field(None, alias="TELEGRAM_PROXY_PORT")
    telegram_proxy_type: str | None = Field(None, alias="TELEGRAM_PROXY_TYPE") # 'socks5', 'http'
    
    # Reddit Settings
    reddit_client_id: str = Field("", alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field("", alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = "slie-bot/0.1"
    
    # SLIE Limits (Updated as per user request)
    max_groups_join_per_day: int = 7
    max_public_replies_per_day: int = 20
    max_dms_per_day: int = 4
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
    dashboard_admin_password: str = Field("changeme", alias="DASHBOARD_ADMIN_PASSWORD")
    dashboard_control_password: str = Field("control-changeme", alias="DASHBOARD_CONTROL_PASSWORD")
    trusted_origins: str | list[str] = Field("https://yourdomain.com", alias="TRUSTED_ORIGINS")
    trusted_hosts: str | list[str] = Field("", alias="TRUSTED_HOSTS")

    # Security (Module 16 Remediation)
    secret_key: str = Field("super-secret-key-change-in-production", alias="SECRET_KEY")
    access_token_expire_minutes: int = 60 * 24 * 7 # 1 week
    dashboard_password_hash: str = Field("", alias="DASHBOARD_PASSWORD_HASH")
    dashboard_control_password_hash: str = Field("", alias="DASHBOARD_CONTROL_PASSWORD_HASH")

    @property
    def trusted_origins_list(self) -> list[str]:
        if isinstance(self.trusted_origins, str):
            return [origin.strip() for origin in self.trusted_origins.split(",") if origin.strip()]
        return self.trusted_origins

    @property
    def trusted_hosts_list(self) -> list[str]:
        raw_hosts = self.trusted_hosts
        if isinstance(raw_hosts, str) and raw_hosts.strip():
            return [host.strip() for host in raw_hosts.split(",") if host.strip()]
        if isinstance(raw_hosts, list) and raw_hosts:
            return raw_hosts

        hosts: list[str] = []
        for origin in self.trusted_origins_list:
            parsed = urlparse(origin if "://" in origin else f"https://{origin}")
            host = parsed.hostname or origin
            if host and host not in hosts:
                hosts.append(host)
        return hosts

    def production_issues(self) -> list[str]:
        if self.environment.lower() != "production":
            return []

        issues: list[str] = []
        secret_key_lower = (self.secret_key or "").lower()
        if (
            not self.secret_key
            or secret_key_lower.startswith("replace-with")
            or self.secret_key == "super-secret-key-change-in-production"
            or len(self.secret_key) < 32
        ):
            issues.append("SECRET_KEY must be a unique production secret with at least 32 characters.")

        password_hash_configured = bool(self.dashboard_password_hash.strip())
        dashboard_password_lower = (self.dashboard_admin_password or "").lower()
        password_is_default = dashboard_password_lower in {"", "changeme", "password", "admin"} or dashboard_password_lower.startswith("replace-with")
        if password_is_default or (not password_hash_configured and len(self.dashboard_admin_password) < 12):
            issues.append("Configure DASHBOARD_PASSWORD_HASH or a strong DASHBOARD_ADMIN_PASSWORD before production.")

        control_hash_configured = bool(self.dashboard_control_password_hash.strip())
        control_password_lower = (self.dashboard_control_password or "").lower()
        control_password_is_default = (
            control_password_lower in {"", "changeme", "control-changeme", "password", "admin"}
            or control_password_lower.startswith("replace-with")
        )
        if control_password_is_default or (not control_hash_configured and len(self.dashboard_control_password) < 12):
            issues.append("Configure DASHBOARD_CONTROL_PASSWORD_HASH or a strong DASHBOARD_CONTROL_PASSWORD before production.")

        db_lower = (self.database_url or "").lower()
        if not db_lower or "postgres:postgres@" in db_lower or "localhost:5432" in db_lower or "127.0.0.1:5432" in db_lower:
            issues.append("DATABASE_URL must point to a real production database, not the local/default database.")
        if self.database_ssl_root_cert.strip() and not Path(self.database_ssl_root_cert).exists():
            issues.append("DATABASE_SSL_ROOT_CERT points to a file that does not exist.")

        # Allow mock Redis as fallback in production if needed
        redis_lower = (self.redis_url or "").lower()
        if not redis_lower or redis_lower.startswith("memory://"):
            pass  # Allow mock, no issue
        elif "localhost:6379" in redis_lower:
            issues.append("REDIS_URL must point to a real production Redis instance, not localhost.")

        origins = self.trusted_origins_list
        if not origins or "*" in origins or any("yourdomain.com" in origin or "localhost" in origin or "127.0.0.1" in origin for origin in origins):
            issues.append("TRUSTED_ORIGINS must contain the real production origin(s), not wildcard/placeholders.")

        hosts = self.trusted_hosts_list
        if not hosts or "*" in hosts or any("yourdomain.com" in host or host in {"localhost", "127.0.0.1"} for host in hosts):
            issues.append("TRUSTED_HOSTS or TRUSTED_ORIGINS must resolve to real production hostnames.")

        return issues

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

    # Rate Limiting
    rate_limit_requests_per_minute: int = Field(60, alias="RATE_LIMIT_REQUESTS_PER_MINUTE")


@lru_cache
def get_settings() -> Settings:
    return Settings()

