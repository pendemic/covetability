from __future__ import annotations

from urllib.parse import urlencode, urlparse

from app.settings import Settings, get_settings

ROVER_BASE_URL = "https://rover.ebay.com/rover/1/711-53200-19255-0/1"


def epn_wrap(item_url: str | None, settings: Settings | None = None) -> str | None:
    if not item_url:
        return None
    current_settings = settings or get_settings()
    if not current_settings.epn_campaign_id:
        return item_url

    parsed = urlparse(item_url)
    if "ebay." not in parsed.netloc.lower():
        return item_url

    query = urlencode(
        {
            "campid": current_settings.epn_campaign_id,
            "customid": current_settings.epn_custom_id,
            "toolid": "10001",
            "mpre": item_url,
        }
    )
    return f"{ROVER_BASE_URL}?{query}"
