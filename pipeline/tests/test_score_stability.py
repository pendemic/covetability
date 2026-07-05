from __future__ import annotations

from datetime import date, timedelta

from app.contract import SearchBucket
from app.models import SearchSignalWeekly, TrendPull
from app.scoring.stability import (
    StabilityBagResult,
    _alias_agreement,
    _decide,
    _flip_rate,
    _reproducibility,
    _window_robustness,
)

WEEK0 = date(2026, 1, 5)


def _signal(bucket: SearchBucket, slope8: float, slope4: float, alias: bool | None) -> SearchSignalWeekly:
    return SearchSignalWeekly(
        bucket=bucket, slope_8w=slope8, slope_4w=slope4, alias_agrees=alias
    )


# --- flip rate ---------------------------------------------------------------


def test_flip_rate_pass_when_stable() -> None:
    signals = [_signal(SearchBucket.up, 1.0, 1.0, True) for _ in range(20)]
    rate, passed = _flip_rate(signals)
    assert rate == 0.0
    assert passed is True


def test_flip_rate_fails_on_noisy_flips() -> None:
    # Alternating buckets with tiny slope moves -> every flip counts (noise).
    signals = []
    for i in range(20):
        bucket = SearchBucket.up if i % 2 == 0 else SearchBucket.flat
        signals.append(_signal(bucket, 0.5 + 0.001 * i, 0.5, True))
    rate, passed = _flip_rate(signals)
    assert rate > 0.25
    assert passed is False


# --- alias + window ----------------------------------------------------------


def test_alias_agreement_fails_on_disagreement() -> None:
    signals = [_signal(SearchBucket.up, 1.0, 1.0, False) for _ in range(10)]
    share, passed = _alias_agreement(signals)
    assert share == 0.0
    assert passed is False


def test_window_robustness_fails_on_opposite_signs() -> None:
    signals = [_signal(SearchBucket.up, 1.0, -1.0, True) for _ in range(10)]
    share, passed = _window_robustness(signals)
    assert share == 0.0
    assert passed is False


# --- reproducibility ---------------------------------------------------------


def _pull(values: list[float]) -> TrendPull:
    points = [{"week": (WEEK0 + timedelta(days=7 * i)).isoformat(), "value": v} for i, v in enumerate(values)]
    return TrendPull(window_start=WEEK0, window_end=WEEK0 + timedelta(days=7 * (len(values) - 1)), weekly_points=points)


def test_reproducibility_pass_with_enough_consistent_trials() -> None:
    base = [40 + 2.6 * i for i in range(18)]  # strong up
    pulls = [_pull([v + (0.5 if t % 2 else -0.5) for v in base]) for t in range(24)]
    trials, share, passed = _reproducibility(pulls)
    assert trials == 24
    assert share >= 0.90
    assert passed is True


def test_reproducibility_fails_with_too_few_trials() -> None:
    base = [40 + 2.6 * i for i in range(18)]
    pulls = [_pull(base) for _ in range(5)]  # < 20 trials
    trials, _share, passed = _reproducibility(pulls)
    assert trials == 5
    assert passed is False


# --- decision ----------------------------------------------------------------


def _result(slug: str, *, flip=True, repro=True, alias=True, window=True) -> StabilityBagResult:
    return StabilityBagResult(
        slug=slug,
        weeks=22,
        flip_rate=0.05,
        flip_pass=flip,
        reproducibility_trials=24,
        reproducibility_share=1.0,
        reproducibility_pass=repro,
        alias_share=1.0,
        alias_pass=alias,
        window_share=1.0,
        window_pass=window,
    )


def test_decision_promotes_to_30_when_all_pass() -> None:
    decision = _decide([_result(f"bag-{i}") for i in range(5)])
    assert decision.recommended_search_weight == 30


def test_decision_flags_at_25_when_alias_fails() -> None:
    per_bag = [_result(f"bag-{i}") for i in range(4)] + [_result("bag-x", alias=False)]
    decision = _decide(per_bag)
    assert decision.recommended_search_weight == 25


def test_decision_demotes_and_excludes_on_flip_failures() -> None:
    two_fail = [_result(f"bag-{i}") for i in range(3)] + [
        _result("a", flip=False),
        _result("b", flip=False),
    ]
    assert _decide(two_fail).recommended_search_weight == 15

    three_fail = [_result(f"bag-{i}") for i in range(2)] + [
        _result("a", flip=False),
        _result("b", flip=False),
        _result("c", flip=False),
    ]
    assert _decide(three_fail).recommended_search_weight == 0
