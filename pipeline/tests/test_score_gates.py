from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.contract import (
    COMPONENT_BREADTH,
    COMPONENT_INVENTORY,
    COMPONENT_KEYS,
    COMPONENT_PRICE,
    SCORE_WEIGHT_CEILINGS,
    ScoreDirection,
)
from app.scoring.confidence import compute_confidence
from app.scoring.gates import redistribute
from app.scoring.smoothing import direction, ema, publication_value

_EPS = 1e-6

# Any eligibility combination.
any_eligibility = st.fixed_dictionaries({key: st.booleans() for key in COMPONENT_KEYS})
# Realistic: breadth is never gated, so a sink always exists.
breadth_eligible = st.fixed_dictionaries(
    {key: (st.just(True) if key == COMPONENT_BREADTH else st.booleans()) for key in COMPONENT_KEYS}
)


# --- gates: property tests ---------------------------------------------------


@given(breadth_eligible)
def test_scored_weights_sum_to_100(eligibility: dict[str, bool]) -> None:
    result = redistribute(eligibility)
    if not result.scored:
        assert sum(1 for v in eligibility.values() if v) < 3
        return
    assert abs(sum(result.weights.values()) - 100.0) < 0.01


@given(any_eligibility)
def test_price_weight_never_exceeds_hard_cap(eligibility: dict[str, bool]) -> None:
    result = redistribute(eligibility)
    assert result.weights[COMPONENT_PRICE] <= SCORE_WEIGHT_CEILINGS[COMPONENT_PRICE] + _EPS


@given(any_eligibility)
def test_fewer_than_three_eligible_is_unscored(eligibility: dict[str, bool]) -> None:
    eligible = [k for k, v in eligibility.items() if v]
    result = redistribute(eligibility)
    if len(eligible) < 3:
        assert result.scored is False
        assert result.unscored_reason is not None
        assert all(v == 0.0 for v in result.weights.values())
    else:
        assert result.scored is True


@given(breadth_eligible)
def test_non_sink_components_respect_ceilings(eligibility: dict[str, bool]) -> None:
    result = redistribute(eligibility)
    if not result.scored:
        return
    for key, weight in result.weights.items():
        if key == result.overflow_to:
            continue
        assert weight <= SCORE_WEIGHT_CEILINGS[key] + _EPS


# --- gates: example cases ----------------------------------------------------


def test_all_eligible_keeps_base_weights() -> None:
    result = redistribute({key: True for key in COMPONENT_KEYS})
    assert result.scored is True
    assert result.overflow_to is None
    assert result.weights == {
        "search_momentum": 25.0,
        "active_inventory_momentum": 25.0,
        "asking_price_momentum": 20.0,
        "marketplace_breadth": 15.0,
        "listing_turnover_proxy": 15.0,
    }


def test_overflow_goes_to_inventory_first() -> None:
    # S, P, I eligible; freed weight from B+T. P is hard-capped at 25, so overflow
    # that cannot fit lands on inventory (first sink in the order).
    result = redistribute(
        {
            "search_momentum": True,
            "active_inventory_momentum": True,
            "asking_price_momentum": True,
            "marketplace_breadth": False,
            "listing_turnover_proxy": False,
        }
    )
    assert result.scored is True
    assert abs(sum(result.weights.values()) - 100.0) < 0.01
    assert result.weights[COMPONENT_PRICE] <= 25 + _EPS
    if result.overflow_to is not None:
        assert result.overflow_to == COMPONENT_INVENTORY


def test_breadth_is_sink_when_inventory_ineligible() -> None:
    # T, P, B eligible (I excluded): ceilings sum to 70 < 100, so breadth absorbs
    # the remainder beyond its nominal ceiling while P stays capped.
    result = redistribute(
        {
            "search_momentum": False,
            "active_inventory_momentum": False,
            "asking_price_momentum": True,
            "marketplace_breadth": True,
            "listing_turnover_proxy": True,
        }
    )
    assert result.scored is True
    assert abs(sum(result.weights.values()) - 100.0) < 0.01
    assert result.weights[COMPONENT_PRICE] <= 25 + _EPS
    assert result.overflow_to == COMPONENT_BREADTH
    assert result.weights[COMPONENT_BREADTH] > SCORE_WEIGHT_CEILINGS[COMPONENT_BREADTH]


# --- confidence --------------------------------------------------------------


def test_confidence_history_cap() -> None:
    result = compute_confidence(
        matched_listing_count=40,
        history_days=30,  # < 90 -> cap 0.60
        average_match_confidence=1.0,
        eligible_component_count=5,
        source_count=5,
        excluded_component_count=0,
    )
    assert result.value <= 0.60
    assert "history_under_90_days" in result.caps_applied


def test_confidence_low_matched_and_two_excluded_take_lowest_cap() -> None:
    result = compute_confidence(
        matched_listing_count=10,  # < 15 -> cap 0.50
        history_days=200,
        average_match_confidence=1.0,
        eligible_component_count=3,
        source_count=5,
        excluded_component_count=2,  # -> cap 0.55
    )
    assert result.value <= 0.50  # lowest cap wins


# --- smoothing ---------------------------------------------------------------


def test_ema_seeds_then_tracks() -> None:
    assert ema(None, 60.0) == 60.0
    stepped = ema(60.0, 80.0, span=7)
    assert 60.0 < stepped < 80.0


def test_publication_value_sticks_until_threshold() -> None:
    assert publication_value(None, 55.0) == 55.0
    assert publication_value(55.0, 56.0) == 55.0  # < 2-point move: sticks
    assert publication_value(55.0, 57.0) == 57.0  # >= 2-point move: updates


def test_direction_from_slope() -> None:
    assert direction([40, 42, 44, 46, 48]) == ScoreDirection.rising
    assert direction([48, 46, 44, 42, 40]) == ScoreDirection.falling
    assert direction([50, 50, 50, 50]) == ScoreDirection.stable
