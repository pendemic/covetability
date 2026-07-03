from __future__ import annotations

import json
import warnings
from collections.abc import Iterable
from pathlib import Path

from app.contract import IngestionMode
from app.ingestion.models import ItemSummary, SearchResponse
from app.ingestion.source import slugify


class FixtureSource:
    source_name = "ebay"
    mode = IngestionMode.fixtures

    def __init__(self, fixtures_dir: Path) -> None:
        self.fixtures_dir = fixtures_dir

    def search_active_listings(self, query: str) -> Iterable[ItemSummary]:
        path = self.fixtures_dir / "search" / f"{slugify(query)}.json"
        if not path.exists():
            warnings.warn(f"Missing eBay fixture for query '{query}': {path}", stacklevel=2)
            return []

        response = SearchResponse.model_validate_json(path.read_text(encoding="utf-8"))
        return response.item_summaries

    def get_item(self, item_id: str) -> ItemSummary:
        for path in (self.fixtures_dir / "search").glob("*.json"):
            response = SearchResponse.model_validate_json(path.read_text(encoding="utf-8"))
            for summary in response.item_summaries:
                if summary.item_id == item_id:
                    return summary

        raise KeyError(f"Fixture item not found: {item_id}")


def write_search_fixture(path: Path, items: list[ItemSummary], query: str) -> None:
    payload = {
        "href": f"fixture://{slugify(query)}",
        "total": len(items),
        "limit": len(items),
        "offset": 0,
        "itemSummaries": [item.model_dump(mode="json", by_alias=True, exclude_none=True) for item in items],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
