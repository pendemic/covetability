from decimal import Decimal

from app.ingestion.models import ItemSummary, to_candidate


def test_browse_summary_normalizes_to_listing_candidate() -> None:
    summary = ItemSummary.model_validate(
        {
            "itemId": "v1|fx-test|0",
            "title": "Chloe Paddington whiskey leather bag",
            "price": {"value": "725.00", "currency": "USD"},
            "itemWebUrl": "https://www.ebay.com/itm/v1-fx-test-0",
            "seller": {"username": "archive-seller"},
            "condition": "Pre-owned - Very Good",
            "shippingOptions": [{"shippingCost": {"value": "22.00", "currency": "USD"}}],
        }
    )

    candidate = to_candidate(summary)

    assert candidate.marketplace_item_id == "v1|fx-test|0"
    assert candidate.price == Decimal("725.00")
    assert candidate.shipping_price == Decimal("22.00")
    assert candidate.shipping_included is False
    assert candidate.seller_id == "archive-seller"
    assert candidate.raw_payload["itemId"] == "v1|fx-test|0"
