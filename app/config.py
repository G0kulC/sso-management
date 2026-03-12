"""
config.py - Application configuration using Pydantic Settings
Reads environment variables with fallback defaults for development
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://sso_user:sso_password@localhost:5432/sso_db"

    # JWT Configuration
    SECRET_KEY: str = "supersecretkey-change-in-production-use-256bit-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Application
    APP_NAME: str = "SSO Identity Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Backend Server
    BACKEND_URL: str = "http://localhost:8000"
    BACKEND_PORT: int = 8000

    # CORS Origins (comma-separated)
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    class Config:
        env_file = ".env"
        case_sensitive = True


# Singleton settings instance
settings = Settings()
