from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable
from typing import Protocol

from app.contract import AuthLabel, IngestionMode
from app.ingestion.models import ItemSummary
from app.settings import Settings


class ListingSource(Protocol):
    source_name: str
    mode: IngestionMode

    def search_active_listings(self, query: str) -> Iterable[ItemSummary]:
        raise NotImplementedError

    def get_item(self, item_id: str) -> ItemSummary:
        raise NotImplementedError

    def image_phash(self, summary: ItemSummary) -> str | None:
        raise NotImplementedError


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized.lower()).strip("-")
    return re.sub(r"-+", "-", slug)


def get_listing_source(settings: Settings) -> ListingSource:
    source = settings.ebay_source.lower()
    if source == IngestionMode.fixtures.value:
        from app.ingestion.fixtures import FixtureSource

        return FixtureSource(settings.resolve_pipeline_path(settings.ebay_fixtures_dir))

    if source == IngestionMode.live.value:
        if not settings.ebay_app_id or not settings.ebay_cert_id:
            raise RuntimeError("EBAY_APP_ID and EBAY_CERT_ID are required when EBAY_SOURCE=live.")

        from app.ingestion.ebay import EbayBrowseClient

        record_dir = (
            settings.resolve_pipeline_path(settings.ebay_record_dir)
            if settings.ebay_record_dir
            else None
        )
        return EbayBrowseClient(
            app_id=settings.ebay_app_id,
            cert_id=settings.ebay_cert_id,
            environment=settings.ebay_environment,
            marketplace_id=settings.ebay_marketplace_id,
            category_ids=settings.ebay_category_ids,
            image_phash_enabled=settings.ebay_image_phash_enabled,
            record_dir=record_dir,
        )

    raise RuntimeError("EBAY_SOURCE must be 'fixtures' or 'live'.")


def load_feed_sources(settings: Settings) -> list[ListingSource]:
    """Build FeedSource instances from the JSON file named by SOURCES_CONFIG."""
    if not settings.sources_config:
        return []
    config_path = settings.resolve_pipeline_path(settings.sources_config)
    if not config_path.exists():
        return []

    from app.ingestion.feed import FeedSource, FeedSourceConfig

    entries = json.loads(config_path.read_text(encoding="utf-8"))
    sources: list[ListingSource] = []
    for entry in entries:
        if entry.get("enabled") is False:
            continue
        sources.append(
            FeedSource(
                FeedSourceConfig(
                    source_name=entry["source_name"],
                    feed_path=entry["feed_path"],
                    columns=entry["columns"],
                    auth_label=AuthLabel(entry.get("auth_label", AuthLabel.authentication_status_unknown.value)),
                    default_currency=entry.get("default_currency", "USD"),
                    delimiter=entry.get("delimiter", ","),
                    gzip=entry.get("gzip", False),
                ),
                base_dir=config_path.parent,
            )
        )
    return sources


def get_listing_sources(settings: Settings) -> list[ListingSource]:
    """The primary source (fixtures / live eBay) plus any configured feed sources."""
    return [get_listing_source(settings), *load_feed_sources(settings)]
