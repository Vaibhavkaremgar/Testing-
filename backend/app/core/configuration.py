import os
from functools import lru_cache
from typing import List, Optional
from urllib.parse import urlsplit

from pydantic import computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _normalize_origin(value: str) -> str:
    cleaned = str(value or "").strip().rstrip("/")
    if not cleaned:
        return ""

    parsed = urlsplit(cleaned)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")

    return cleaned


class Settings(BaseSettings):
    APP_NAME: str = "TalentAI Recruitment System"
    DEBUG: bool = True
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "talentai")

    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "your-secret-key-min-32-characters-long-change-this-in-production",
    )
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 30))
    )

    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/data")
    MAX_FILE_SIZE: int = 10 * 1024 * 1024
    RESUME_UPLOAD_MAX_BYTES: int = int(os.getenv("RESUME_UPLOAD_MAX_BYTES", str(5 * 1024 * 1024)))
    NLP_MAX_TEXT_LENGTH: int = int(os.getenv("NLP_MAX_TEXT_LENGTH", "2000"))

    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq")

    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    RESEND_API_URL: str = os.getenv("RESEND_API_URL", "https://api.resend.com/emails")
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    SENDGRID_API_URL: str = os.getenv(
        "SENDGRID_API_URL",
        "https://api.sendgrid.com/v3/mail/send",
    )
    SMTP_TIMEOUT_SECONDS: int = int(os.getenv("SMTP_TIMEOUT_SECONDS", "20"))
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "noreply@yourcompany.com")
    FROM_NAME: str = os.getenv("FROM_NAME", "TalentAI Recruitment")
    SLOT_BOOKING_URL: str = os.getenv(
        "SLOT_BOOKING_URL",
        "https://pontis-backend-production.up.railway.app/booking.html",
    )
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://dashboard.pontis.one")
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "https://domain.com")
    INTERNAL_SERVICE_TOKEN: str = os.getenv("INTERNAL_SERVICE_TOKEN", "")
    RECORDING_SERVICE_TOKEN: str = os.getenv(
        "RECORDING_SERVICE_TOKEN",
        os.getenv("INTERNAL_SERVICE_TOKEN", ""),
    )
    RECORDING_BASE_URL: str = os.getenv(
        "RECORDING_BASE_URL",
        "https://interview.pontis.one",
    )

    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "")
    CORS_ALLOW_RAILWAY_PREVIEWS: bool = (
        os.getenv("CORS_ALLOW_RAILWAY_PREVIEWS", "false").strip().lower()
        in {"1", "true", "yes", "on"}
    )

    JOB_FEED_DEFAULT_STATUS: str = os.getenv("JOB_FEED_DEFAULT_STATUS", "active")
    JOB_FEED_PAGE_SIZE: int = int(os.getenv("JOB_FEED_PAGE_SIZE", "20"))
    JOB_FEED_MAX_PAGE_SIZE: int = int(os.getenv("JOB_FEED_MAX_PAGE_SIZE", "100"))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        if isinstance(value, bool):
            return value
        if value is None:
            return True

        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug", "development", "dev"}:
            return True
        if normalized in {"0", "false", "no", "off", "release", "production", "prod"}:
            return False
        return value

    @computed_field
    @property
    def resolved_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL

        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )

    @property
    def environment_name(self) -> str:
        return str(self.ENVIRONMENT or "").strip().lower()

    @property
    def is_production(self) -> bool:
        return self.environment_name in {"production", "prod"} or not self.DEBUG

    @property
    def default_allowed_origins(self) -> List[str]:
        production_origins = ["https://dashboard.pontis.one"]
        development_origins = [
            "http://localhost:3000",
            "http://localhost:4173",
            "http://localhost:5173",
            "http://localhost:5174",
        ]
        return production_origins if self.is_production else [*production_origins, *development_origins]

    @property
    def allowed_origins_list(self) -> List[str]:
        origins: List[str] = []

        for origin in self.default_allowed_origins:
            cleaned = _normalize_origin(origin)
            if cleaned and cleaned not in origins:
                origins.append(cleaned)

        for origin in self.ALLOWED_ORIGINS.split(","):
            cleaned = _normalize_origin(origin)
            if cleaned and cleaned not in origins:
                origins.append(cleaned)

        frontend_origin = _normalize_origin(self.FRONTEND_URL)
        if frontend_origin and frontend_origin not in origins:
            origins.append(frontend_origin)

        return origins

    @property
    def allowed_origin_regex(self) -> Optional[str]:
        if self.CORS_ALLOW_RAILWAY_PREVIEWS:
            return r"https://.*\.railway\.app"
        return None


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
