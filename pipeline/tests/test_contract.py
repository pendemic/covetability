from app import contract
from app.models import DailyAggregate


def test_contract_constants_match_governing_docs() -> None:
    assert contract.MIN_LISTINGS_PER_BAND == 5
    assert contract.MIN_MODEL_WIDE_LISTINGS == 8
    assert contract.MIN_LIFECYCLE_EVENTS == 15
    assert contract.MATCH_AUTO_ACCEPT == 0.90
    assert contract.MATCH_REVIEW_FLOOR == 0.60
    assert contract.REMATCH_DELTA_THRESHOLD == 0.15
    assert contract.MATCH_PRECISION_TARGET == 0.95
    assert contract.MATCH_RECALL_TARGET == 0.70
    assert contract.VARIANT_ATTRIBUTION_TARGET == 0.85
    assert contract.WINSOR_PCT == (2, 98)
    assert contract.RAW_RETENTION_DAYS == 90
    assert contract.RELIST_WINDOW_DAYS == 14
    assert contract.AGGREGATE_WINDOW_DAYS == 14
    assert contract.SCORE_BASE_WEIGHTS == {
        "search_momentum": 25,
        "active_inventory_momentum": 25,
        "asking_price_momentum": 20,
        "marketplace_breadth": 15,
        "listing_turnover_proxy": 15,
    }
    assert contract.SCORE_WEIGHT_CEILINGS["asking_price_momentum"] == 25
    assert contract.CONDITION_ACCURACY_TARGET == 0.85
    assert contract.PHASH_HAMMING_MAX == 6
    assert contract.PUBLIC_HISTORY_DEFAULT_DAYS == 90
    assert contract.PUBLIC_HISTORY_MAX_DAYS == 365


def test_matching_contract_enums_are_stable() -> None:
    assert [status.value for status in contract.MatchStatus] == [
        "pending",
        "auto_accepted",
        "needs_review",
        "auto_rejected",
        "human_accepted",
        "human_rejected",
    ]
    assert [origin.value for origin in contract.GoldLabelOrigin] == [
        "labeling_ui",
        "review_queue",
        "fixture_seed",
    ]


def test_condition_band_order_is_scale_order() -> None:
    assert [band.value for band in contract.ConditionBand] == [
        "new_or_unused",
        "excellent",
        "very_good",
        "good",
        "fair",
        "poor",
    ]


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
