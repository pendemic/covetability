from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    database_url: str = Field(
        default="postgresql+psycopg://covetability:covetability@localhost:55432/covetability",
        alias="DATABASE_URL",
    )
    # Tests run against this DB, never the main one (they truncate/rematch data).
    # Defaults to None; conftest requires it to be set and different from database_url.
    test_database_url: str | None = Field(default=None, alias="TEST_DATABASE_URL")
    admin_secret: str = Field(default="change-me", alias="ADMIN_SECRET")
    ebay_app_id: str | None = Field(default=None, alias="EBAY_APP_ID")
    ebay_cert_id: str | None = Field(default=None, alias="EBAY_CERT_ID")
    ebay_dev_id: str | None = Field(default=None, alias="EBAY_DEV_ID")
    ebay_environment: str = Field(default="production", alias="EBAY_ENVIRONMENT")
    ebay_source: str = Field(default="fixtures", alias="EBAY_SOURCE")
    ebay_marketplace_id: str = Field(default="EBAY_US", alias="EBAY_MARKETPLACE_ID")
    ebay_category_ids: str = Field(default="169291", alias="EBAY_CATEGORY_IDS")
    ebay_fixtures_dir: str = Field(default="fixtures/ebay", alias="EBAY_FIXTURES_DIR")
    ebay_record_dir: str | None = Field(default=None, alias="EBAY_RECORD_DIR")
    ebay_image_phash_enabled: bool = Field(default=True, alias="EBAY_IMAGE_PHASH_ENABLED")
    # JSON file listing additional affiliate-feed sources (Vestiaire, TRR, …).
    # See sources.example.json. Absent/empty ⇒ eBay only.
    sources_config: str | None = Field(default=None, alias="SOURCES_CONFIG")
    trends_source: str = Field(default="fixtures", alias="TRENDS_SOURCE")
    trends_fixtures_dir: str = Field(default="fixtures/trends", alias="TRENDS_FIXTURES_DIR")
    trends_csv_dir: str | None = Field(default=None, alias="TRENDS_CSV_DIR")
    trends_anchor_term: str = Field(default="handbag", alias="TRENDS_ANCHOR_TERM")
    epn_campaign_id: str | None = Field(default=None, alias="EPN_CAMPAIGN_ID")
    epn_custom_id: str = Field(default="covetability", alias="EPN_CUSTOM_ID")
    analytics_domain: str | None = Field(default=None, alias="ANALYTICS_DOMAIN")
    analytics_src: str = Field(default="https://plausible.io/js/script.js", alias="ANALYTICS_SRC")

    @property
    def package_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def resolve_pipeline_path(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return self.package_root / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
