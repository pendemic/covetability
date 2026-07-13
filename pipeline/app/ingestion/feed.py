"""Affiliate product-feed source.

Most non-eBay resale sites (Vestiaire Collective, The RealReal, Fashionphile,
Rebag, Poshmark/Mercari) don't expose an open item API but *do* publish product
feeds through affiliate networks (CJ, Impact, Awin, Rakuten) as downloadable
CSV/TSV. This adapter ingests such a feed: it reads the file once, maps columns
via a per-source config, and filters catalog rows against each bag's queries —
so adding a source is just a feed file + a column map, no new code.

Configure sources in the JSON file named by ``SOURCES_CONFIG`` (see
``sources.example.json``).
"""

from __future__ import annotations

import csv
import gzip
import io
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

import httpx

from app.contract import AuthLabel, IngestionMode
from app.ingestion.models import Image, ItemSummary, Money, Seller

_PRICE_RE = re.compile(r"[0-9]+(?:[.,][0-9]+)?")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _fold(text: str) -> str:
    """Lowercase and strip accents so 'Chloé' matches the query token 'chloe'."""
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text.lower()) if not unicodedata.combining(ch)
    )


@dataclass(frozen=True)
class FeedSourceConfig:
    source_name: str
    # Local path (absolute or relative to the config file) OR an http(s) URL.
    # Gzipped feeds (.gz) are decompressed automatically.
    feed_path: str
    # Maps our fields -> the feed's column headers.
    columns: dict[str, str]
    auth_label: AuthLabel = AuthLabel.authentication_status_unknown
    default_currency: str = "USD"
    delimiter: str = ","
    gzip: bool = False


class FeedSource:
    """Reads an affiliate product feed and exposes it as a ListingSource."""

    mode = IngestionMode.live

    def __init__(self, config: FeedSourceConfig, *, base_dir: Path | None = None) -> None:
        self.config = config
        self.source_name = config.source_name
        self._base_dir = base_dir
        self._rows: list[ItemSummary] | None = None

    def _is_url(self) -> bool:
        return self.config.feed_path.lower().startswith(("http://", "https://"))

    def _resolve(self) -> Path:
        path = Path(self.config.feed_path)
        if path.is_absolute() or self._base_dir is None:
            return path
        return self._base_dir / path

    def _raw_bytes(self) -> bytes:
        if self._is_url():
            response = httpx.get(self.config.feed_path, timeout=120, follow_redirects=True)
            response.raise_for_status()
            return response.content
        return self._resolve().read_bytes()

    def _text(self) -> str:
        data = self._raw_bytes()
        gzipped = self.config.gzip or self.config.feed_path.lower().endswith(".gz")
        # Also detect gzip magic bytes so a mislabeled config still works.
        if gzipped or data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        return data.decode("utf-8-sig", errors="replace")

    def _load(self) -> list[ItemSummary]:
        if self._rows is not None:
            return self._rows
        rows: list[ItemSummary] = []
        cols = self.config.columns
        reader = csv.DictReader(io.StringIO(self._text()), delimiter=self.config.delimiter)
        for raw in reader:
            summary = self._to_summary(raw, cols)
            if summary is not None:
                rows.append(summary)
        self._rows = rows
        return rows

    def _to_summary(self, raw: dict[str, str], cols: dict[str, str]) -> ItemSummary | None:
        def col(field_name: str) -> str | None:
            key = cols.get(field_name)
            if key is None:
                return None
            value = raw.get(key)
            return value.strip() if isinstance(value, str) else value

        item_id = col("id")
        title = col("title")
        price = parse_price(col("price"))
        if not item_id or not title or price is None:
            return None
        currency = col("currency") or self.config.default_currency
        image_url = col("image")
        seller = col("seller")
        return ItemSummary.model_validate(
            {
                "itemId": f"{self.source_name}:{item_id}",
                "title": title,
                "price": Money(value=price, currency=currency),
                "itemWebUrl": col("url"),
                "condition": col("condition"),
                "seller": Seller(username=seller) if seller else None,
                "image": Image(imageUrl=image_url) if image_url else None,
                "authHint": self.config.auth_label,
            }
        )

    def search_active_listings(self, query: str) -> Iterable[ItemSummary]:
        # Feeds are the whole catalog; approximate a search by requiring every
        # distinctive query token (len >= 4) to appear in the title. Accent-folded
        # so 'chloe' matches 'Chloé'.
        tokens = [tok for tok in _TOKEN_RE.findall(_fold(query)) if len(tok) >= 4]
        if not tokens:
            return []
        matches: list[ItemSummary] = []
        for summary in self._load():
            title = _fold(summary.title)
            if all(tok in title for tok in tokens):
                matches.append(summary)
        return matches

    def get_item(self, item_id: str) -> ItemSummary:
        for summary in self._load():
            if summary.item_id == item_id:
                return summary
        raise KeyError(item_id)

    def image_phash(self, summary: ItemSummary) -> str | None:
        return None


def parse_price(value: str | None) -> Decimal | None:
    if not value:
        return None
    match = _PRICE_RE.search(value.replace(",", ""))
    if not match:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None
