from __future__ import annotations

import base64
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from app.contract import IngestionMode
from app.ingestion.fixtures import write_search_fixture
from app.ingestion.models import ItemSummary, SearchResponse
from app.ingestion.phash import compute_phash
from app.ingestion.source import slugify

OAUTH_SCOPE = "https://api.ebay.com/oauth/api_scope"


class EbayApiError(RuntimeError):
    pass


class EbayBrowseClient:
    source_name = "ebay"
    mode = IngestionMode.live

    def __init__(
        self,
        *,
        app_id: str,
        cert_id: str,
        environment: str = "production",
        marketplace_id: str = "EBAY_US",
        category_ids: str = "169291",
        record_dir: Path | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.app_id = app_id
        self.cert_id = cert_id
        self.environment = environment
        self.marketplace_id = marketplace_id
        self.category_ids = category_ids
        self.record_dir = record_dir
        self._access_token: str | None = None
        self._token_expires_at = datetime.min.replace(tzinfo=UTC)
        self.client = httpx.Client(base_url=self.base_url, timeout=30, transport=transport)

    @property
    def base_url(self) -> str:
        if self.environment == "sandbox":
            return "https://api.sandbox.ebay.com"
        return "https://api.ebay.com"

    def search_active_listings(self, query: str) -> list[ItemSummary]:
        items: list[ItemSummary] = []
        offset = 0
        limit = 200

        while offset < 1000:
            response = self._request_search_page(query=query, limit=limit, offset=offset)
            items.extend(response.item_summaries)
            if not response.next:
                break
            offset += limit

        if self.record_dir is not None:
            write_search_fixture(self.record_dir / "search" / f"{slugify(query)}.json", items, query)

        return items

    def get_item(self, item_id: str) -> ItemSummary:
        response = self._request("GET", f"/buy/browse/v1/item/{item_id}")
        return ItemSummary.model_validate(response.json())

    def image_phash(self, summary: ItemSummary) -> str | None:
        if summary.image is None or summary.image.image_url is None:
            return None
        try:
            response = self.client.get(summary.image.image_url, timeout=15)
            response.raise_for_status()
            return compute_phash(response.content)
        except Exception:
            return None

    def _request_search_page(self, *, query: str, limit: int, offset: int) -> SearchResponse:
        response = self._request(
            "GET",
            "/buy/browse/v1/item_summary/search",
            params={
                "q": query,
                "category_ids": self.category_ids,
                "filter": "buyingOptions:{FIXED_PRICE|BEST_OFFER}",
                "limit": str(limit),
                "offset": str(offset),
            },
        )
        return SearchResponse.model_validate(response.json())

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        headers.update(
            {
                "Authorization": f"Bearer {self._token()}",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
            }
        )
        response = self.client.request(method, path, headers=headers, **kwargs)

        if response.status_code == 401:
            self._access_token = None
            headers["Authorization"] = f"Bearer {self._token()}"
            response = self.client.request(method, path, headers=headers, **kwargs)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "1"))
            time.sleep(min(retry_after, 5))
            raise EbayApiError("eBay Browse API rate limit exceeded.")

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise EbayApiError(f"eBay Browse API request failed: {exc.response.text}") from exc

        return response

    def _token(self) -> str:
        if self._access_token and datetime.now(UTC) < self._token_expires_at:
            return self._access_token

        auth = base64.b64encode(f"{self.app_id}:{self.cert_id}".encode()).decode("ascii")
        response = self.client.post(
            "/identity/v1/oauth2/token",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials", "scope": OAUTH_SCOPE},
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise EbayApiError(f"eBay OAuth failed: {exc.response.text}") from exc

        payload = response.json()
        self._access_token = payload["access_token"]
        expires_in = int(payload.get("expires_in", 7200))
        self._token_expires_at = datetime.now(UTC) + timedelta(seconds=max(expires_in - 60, 60))
        return self._access_token
