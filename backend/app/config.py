from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List
import os

class Settings(BaseSettings):
    APP_NAME: str = "TalentAI Recruitment System"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite:///./talentai.db"
    
    # JWT
    SECRET_KEY: str = "your-secret-key-min-32-characters-long-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days
    
    # File Upload
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # LLM Configuration
    GROQ_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    LLM_PROVIDER: str = "groq"
    
    # CORS
<<<<<<< HEAD
    # ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost:4173,https://glistening-youth-production.up.railway.app,http://localhost:5174"
    ALLOWED_ORIGINS: str = "https://glistening-youth-production.up.railway.app,http://localhost:5173,http://localhost:3000,http://localhost:4173,http://localhost:5174"
=======
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost:4173,https://glistening-youth-production.up.railway.app,http://localhost:5174"
>>>>>>> 8c388104a03f506429820a154d4322d9bf5b4396
    
    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
