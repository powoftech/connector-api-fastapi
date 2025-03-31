from functools import lru_cache

from pydantic import EmailStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    
    # PostgreSQL
    database_url_async: str = ""

    # Redis
    redis_url: str = ""

    # JWT
    jwt_algorithm: str = ""
    jwt_secret_key: str = ""

    # Email (Resend)
    resend_api_key: str = ""
    sender_email: EmailStr = ""

    verification_email_expiry_minutes: int = 30
    access_token_expiry_minutes: int = 15
    refresh_token_expiry_days: int = 30

    model_config = SettingsConfigDict(
        env_file=(".env"),
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings():
    return Settings()
