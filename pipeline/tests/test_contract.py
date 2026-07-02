from app import contract
from app.models import DailyAggregate


def test_contract_constants_match_governing_docs() -> None:
    assert contract.MIN_LISTINGS_PER_BAND == 5
    assert contract.MIN_MODEL_WIDE_LISTINGS == 8
    assert contract.MIN_LIFECYCLE_EVENTS == 15
    assert contract.MATCH_AUTO_ACCEPT == 0.90
    assert contract.MATCH_REVIEW_FLOOR == 0.60
    assert contract.WINSOR_PCT == (2, 98)
    assert contract.RAW_RETENTION_DAYS == 90
    assert contract.RELIST_WINDOW_DAYS == 14
    assert contract.SCORE_BASE_WEIGHTS == {
        "search_momentum": 25,
        "active_inventory_momentum": 25,
        "asking_price_momentum": 20,
        "marketplace_breadth": 15,
        "listing_turnover_proxy": 15,
    }
    assert contract.SCORE_WEIGHT_CEILINGS["asking_price_momentum"] == 25


def test_daily_aggregate_model_avoids_prohibited_metric_language() -> None:
    prohibited = {
        "market_value",
        "worth",
        "valuation",
        "sold",
        "sell_through",
        "sales",
        "sales_rate",
        "demand",
        "investment",
        "appreciating",
        "roi",
        "forecast",
        "prediction",
    }
    names = {column.name for column in DailyAggregate.__table__.columns}
    names.update(DailyAggregate.__mapper__.attrs.keys())

    assert names.isdisjoint(prohibited)
