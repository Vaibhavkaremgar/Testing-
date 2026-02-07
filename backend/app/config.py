from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "TalentAI Recruitment System"
    DEBUG: bool = True
    
    # Database
    DATABASE_URL: str = "sqlite:///./talentai.db"
    
    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production-use-openssl-rand-hex-32"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # File Upload
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # LLM Configuration
    GROQ_API_KEY: str = ""  # Add your Groq API key here or in .env
    OPENAI_API_KEY: str = ""  # Alternative: OpenAI API key
    LLM_PROVIDER: str = "groq"  # Options: groq, openai, ollama
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
