from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.contract import ConditionBand
from app.insights.observations import generate_observations
from app.models import DailyAggregate


def aggregate(day: date, band: ConditionBand, median: str | None, active: int, new: int = 0) -> DailyAggregate:
    return DailyAggregate(
        bag_model_id=1,
        variant_id=None,
        condition_band=band,
        observation_date=day,
        active_listing_count=active,
        new_listing_count=new,
        matched_listing_count=5 if median is not None else 3,
        median_asking_price=Decimal(median) if median is not None else None,
        p25_asking_price=Decimal("90.00") if median is not None else None,
        p75_asking_price=Decimal("120.00") if median is not None else None,
        source_count=1,
    )


def test_observations_are_templated_and_exclude_thin_band() -> None:
    as_of = date(2026, 7, 20)
    rows = [
        aggregate(date(2026, 7, 6), ConditionBand.good, "100.00", 7),
        aggregate(as_of, ConditionBand.good, "125.00", 9, new=2),
        aggregate(date(2026, 7, 6), ConditionBand.fair, None, 2),
        aggregate(as_of, ConditionBand.fair, None, 3),
    ]

    observations = generate_observations(rows, as_of)
    sentences = [item["sentence"] for item in observations]

    assert "Good median asking moved up 25.0% over 14 days." in sentences
    assert all("Fair median" not in sentence for sentence in sentences)
    assert len(observations) <= 5
