from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    database_url: str = Field(
        default="postgresql+psycopg://covetability:covetability@localhost:55432/covetability",
        alias="DATABASE_URL",
    )
    admin_secret: str = Field(default="change-me", alias="ADMIN_SECRET")
    ebay_app_id: str | None = Field(default=None, alias="EBAY_APP_ID")
    ebay_cert_id: str | None = Field(default=None, alias="EBAY_CERT_ID")
    ebay_dev_id: str | None = Field(default=None, alias="EBAY_DEV_ID")
    ebay_environment: str = Field(default="production", alias="EBAY_ENVIRONMENT")


@lru_cache
def get_settings() -> Settings:
    return Settings()
