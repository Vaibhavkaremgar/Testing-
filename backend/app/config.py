from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List
import os

class Settings(BaseSettings):
    APP_NAME: str = "TalentAI Recruitment System"
    DEBUG: bool = True
    
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
    
    # SMTP Email Configuration
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
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
