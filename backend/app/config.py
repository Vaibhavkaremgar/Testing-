from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List
import os

class Settings(BaseSettings):
    APP_NAME: str = "TalentAI Recruitment System"
    DEBUG: bool = True

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
    
    # LLM Configuration
    GROQ_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    LLM_PROVIDER: str = "groq"
    
    # Gmail SMTP Email Configuration
    GMAIL_SENDER: str = os.getenv("GMAIL_SENDER", "")
    GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "noreply@yourcompany.com")
    FROM_NAME: str = os.getenv("FROM_NAME", "TalentAI Recruitment")
    SLOT_BOOKING_URL: str = os.getenv("SLOT_BOOKING_URL", "http://localhost:3000/booking.html")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "https://glistening-youth-production.up.railway.app")
    
    # CORS
    ALLOWED_ORIGINS: str = "https://glistening-youth-production.up.railway.app,http://localhost:5173,http://localhost:3000,http://localhost:4173,http://localhost:5174"
    
    @property
    def allowed_origins_list(self) -> List[str]:
        origins = []
        for origin in self.ALLOWED_ORIGINS.split(","):
            cleaned = origin.strip().rstrip("/")
            if cleaned:
                origins.append(cleaned)

        frontend_origin = self.FRONTEND_URL.strip().rstrip("/")
        if frontend_origin and frontend_origin not in origins:
            origins.append(frontend_origin)

        return origins
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
