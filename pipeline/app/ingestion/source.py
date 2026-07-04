from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Protocol

from app.contract import IngestionMode
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
            record_dir=record_dir,
        )

    raise RuntimeError("EBAY_SOURCE must be 'fixtures' or 'live'.")
