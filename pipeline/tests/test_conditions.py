from app.conditions.normalize import band_distance, normalize_condition
from app.contract import ConditionBand, ConditionConfidence


def test_structured_condition_maps_to_band_with_high_confidence() -> None:
    assessment = normalize_condition(
        "Pre-owned - Very Good",
        "Balenciaga Classic City black lambskin motorcycle bag mirror",
        bag_slug="balenciaga-city",
    )

    assert assessment.band == ConditionBand.very_good
    assert assessment.confidence == ConditionConfidence.high


def test_damage_keywords_cap_structured_condition_downward() -> None:
    assessment = normalize_condition(
        "Pre-owned - Excellent",
        "Fendi Baguette vintage sticky lining as-is",
        bag_slug="fendi-baguette",
    )

    assert assessment.band == ConditionBand.fair
    assert assessment.confidence == ConditionConfidence.medium
    assert {signal.term for signal in assessment.signals} >= {"sticky lining", "as is"}


def test_bare_preowned_uses_title_keywords_or_abstains() -> None:
    positive = normalize_condition(
        "Pre-owned",
        "Chloe Paddington whiskey satchel full set lock key cards dust bag",
        bag_slug="chloe-paddington",
    )
    empty = normalize_condition("Pre-owned", "Chloe Paddington brown satchel", bag_slug="chloe-paddington")

    assert positive.band == ConditionBand.excellent
    assert positive.confidence == ConditionConfidence.low
    assert empty.band is None
    assert empty.confidence == ConditionConfidence.indeterminate


def test_band_distance_counts_adjacent_bands() -> None:
    assert band_distance(ConditionBand.excellent, ConditionBand.very_good) == 1
    assert band_distance(ConditionBand.excellent, ConditionBand.fair) == 3
