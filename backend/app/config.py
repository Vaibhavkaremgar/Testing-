import os
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "TalentAI Recruitment System"
    DEBUG: bool = True
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, value):
        """Accept common deployment strings like 'release' without crashing startup."""
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
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:AKwoGijyptKJZVJiPBWUjeGDuqfnXwXD@postgres.railway.internal:5432/railway")
    
    # JWT
    SECRET_KEY: str = "your-secret-key-min-32-characters-long-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days
    
    # File Upload
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "/data")  # Railway volume mount
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    NLP_MAX_TEXT_LENGTH: int = int(os.getenv("NLP_MAX_TEXT_LENGTH", "4000"))
    
    # LLM Configuration
    GROQ_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    LLM_PROVIDER: str = "groq"
    
    # Transactional email configuration
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    RESEND_API_URL: str = os.getenv("RESEND_API_URL", "https://api.resend.com/emails")
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    SENDGRID_API_URL: str = os.getenv("SENDGRID_API_URL", "https://api.sendgrid.com/v3/mail/send")
    SMTP_TIMEOUT_SECONDS: int = int(os.getenv("SMTP_TIMEOUT_SECONDS", "20"))
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "noreply@yourcompany.com")
    FROM_NAME: str = os.getenv("FROM_NAME", "TalentAI Recruitment")
    SLOT_BOOKING_URL: str = os.getenv("SLOT_BOOKING_URL", "https://pontis-backend-production.up.railway.app/booking.html")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://dashboard.pontis.one")
    INTERNAL_SERVICE_TOKEN: str = os.getenv("INTERNAL_SERVICE_TOKEN", "")
    INTERNAL_RECORDING_BASE_URL: str = os.getenv("INTERNAL_RECORDING_BASE_URL", "http://pontis-backend.railway.internal")
    INTERNAL_RECORDING_FALLBACK_BASE_URL: str = os.getenv("INTERNAL_RECORDING_FALLBACK_BASE_URL", "https://interview.pontis.one")
    
    # CORS
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "")
    CORS_ALLOW_RAILWAY_PREVIEWS: bool = os.getenv("CORS_ALLOW_RAILWAY_PREVIEWS", "false").strip().lower() in {"1", "true", "yes", "on"}

    @property
    def environment_name(self) -> str:
        return str(self.ENVIRONMENT or "").strip().lower()

    @property
    def is_production(self) -> bool:
        return self.environment_name in {"production", "prod"} or not self.DEBUG

    @property
    def default_allowed_origins(self) -> List[str]:
        production_origins = [
            "https://dashboard.pontis.one",
        ]
        development_origins = [
            "http://localhost:3000",
            "http://localhost:4173",
            "http://localhost:5173",
            "http://localhost:5174",
        ]
        return production_origins if self.is_production else [*production_origins, *development_origins]
    
    
    @property
    def allowed_origins_list(self) -> List[str]:
        origins = []
        for origin in self.default_allowed_origins:
            cleaned = origin.strip().rstrip("/")
            if cleaned and cleaned not in origins:
                origins.append(cleaned)

        for origin in self.ALLOWED_ORIGINS.split(","):
            cleaned = origin.strip().rstrip("/")
            if cleaned and cleaned not in origins:
                origins.append(cleaned)

        frontend_origin = self.FRONTEND_URL.strip().rstrip("/")
        if frontend_origin and frontend_origin not in origins:
            origins.append(frontend_origin)

        return origins

    @property
    def allowed_origin_regex(self) -> Optional[str]:
        if self.CORS_ALLOW_RAILWAY_PREVIEWS:
            return r"https://.*\.railway\.app"
        return None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
