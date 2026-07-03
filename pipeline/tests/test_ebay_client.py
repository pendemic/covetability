from __future__ import annotations

import json

import httpx
import pytest

from app.ingestion.ebay import EbayApiError, EbayBrowseClient


def token_response() -> httpx.Response:
    return httpx.Response(200, json={"access_token": "token-1", "expires_in": 7200})


def search_response(*, next_page: bool = False) -> httpx.Response:
    payload = {
        "href": "https://api.ebay.com/buy/browse/v1/item_summary/search",
        "total": 1,
        "limit": 200,
        "offset": 0,
        "itemSummaries": [
            {
                "itemId": "v1|fx-ebay-client|0",
                "title": "Dior Saddle vintage blue oblique",
                "price": {"value": "1500.00", "currency": "USD"},
                "condition": "Pre-owned",
            }
        ],
    }
    if next_page:
        payload["next"] = "https://api.ebay.com/buy/browse/v1/item_summary/search?offset=200"
    return httpx.Response(200, json=payload)


def test_ebay_client_caches_token_and_paginates() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/identity/v1/oauth2/token"):
            return token_response()
        offset = request.url.params.get("offset")
        return search_response(next_page=offset == "0")

    client = EbayBrowseClient(
        app_id="app",
        cert_id="cert",
        transport=httpx.MockTransport(handler),
    )

    items = client.search_active_listings("dior saddle bag")

    assert len(items) == 2
    token_requests = [request for request in requests if request.url.path.endswith("/token")]
    assert len(token_requests) == 1
    search_offsets = [
        request.url.params["offset"]
        for request in requests
        if request.url.path.endswith("/item_summary/search")
    ]
    assert search_offsets == ["0", "200"]


def test_ebay_client_reauths_once_on_401() -> None:
    search_attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal search_attempts
        if request.url.path.endswith("/identity/v1/oauth2/token"):
            return token_response()
        search_attempts += 1
        if search_attempts == 1:
            return httpx.Response(401, json={"error": "expired"})
        return search_response()

    client = EbayBrowseClient(
        app_id="app",
        cert_id="cert",
        transport=httpx.MockTransport(handler),
    )

    assert len(client.search_active_listings("dior saddle bag")) == 1
    assert search_attempts == 2


def test_ebay_client_raises_on_429() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/identity/v1/oauth2/token"):
            return token_response()
        return httpx.Response(429, headers={"Retry-After": "0"}, json={"error": "rate limit"})

    client = EbayBrowseClient(
        app_id="app",
        cert_id="cert",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(EbayApiError):
        client.search_active_listings("dior saddle bag")


def test_ebay_client_records_fixture_compatible_payload(tmp_path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/identity/v1/oauth2/token"):
            return token_response()
        return search_response()

    client = EbayBrowseClient(
        app_id="app",
        cert_id="cert",
        record_dir=tmp_path,
        transport=httpx.MockTransport(handler),
    )

    client.search_active_listings("dior saddle bag")
    payload = json.loads((tmp_path / "search" / "dior-saddle-bag.json").read_text())

    assert payload["itemSummaries"][0]["itemId"] == "v1|fx-ebay-client|0"
