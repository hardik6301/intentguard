from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./intentguard.db"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    payment_provider: str = "simulated"
    grant_ttl_seconds: int = 600
    intent_ttl_seconds: int = 3600
    grant_signing_secret: str = "intentguard-dev-grant"


def get_settings() -> Settings:
    return Settings()
