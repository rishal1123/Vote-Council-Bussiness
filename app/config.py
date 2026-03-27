from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    APP_NAME: str = "VoteCouncil"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./votecouncil.db"

    # JWT Settings
    SECRET_KEY: str = "your-secret-key-change-in-production-use-strong-random-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Cookie security — set False when Cloudflare connects to backend via HTTP
    COOKIE_SECURE: bool = False

    # File Upload
    UPLOAD_DIR: Path = Path("uploads")
    MAX_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5MB
    ALLOWED_EXTENSIONS: set = {"jpg", "jpeg", "png", "gif"}

    class Config:
        env_file = ".env"


settings = Settings()

# Ensure upload directory exists
settings.UPLOAD_DIR.mkdir(exist_ok=True)
