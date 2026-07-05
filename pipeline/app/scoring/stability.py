"""Search-signal stability gate harness (score-spec §6).

Runs the four pre-launch tests on the pilot bags and produces the documented
weight decision for the search component S. The goal is not zero bucket changes
— a trend signal must move when behaviour moves — but that changes not be
dominated by sampling noise.

Tests, per bag:
  1. Per-bag stability: bucket flips in < 25% of weekly transitions, excluding
     transitions where the 8-week slope also moved by > 1.5x its trailing std.
  2. Pull reproducibility: repeated same-window pulls land within 1 bucket in
     >= 90% of trials (>= 20 trials).
  3. Alias agreement: canonical and top-alias agree in direction in >= 75% of weeks.
  4. Window robustness: 4-week and 8-week slopes agree in sign in >= 70% of weeks.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contract import (
    SEARCH_WEIGHT_BASE,
    SEARCH_WEIGHT_DEMOTED,
    SEARCH_WEIGHT_FULL,
    STABILITY_ALIAS_AGREEMENT_MIN,
    STABILITY_BAGS_REQUIRED,
    STABILITY_FLIP_RATE_MAX,
    STABILITY_REPRODUCIBILITY_MIN_SHARE,
    STABILITY_REPRODUCIBILITY_MIN_TRIALS,
    STABILITY_SLOPE_CHANGE_EXEMPTION,
    STABILITY_WINDOW_ROBUSTNESS_MIN,
    SearchBucket,
    TrendQueryRole,
)
from app.models import BagModel, SearchSignalWeekly, TrendPull
from app.scoring.util import linear_slope, stdev
from app.trends.classify import bucket_for_slope

_BUCKET_ORDINAL = {
    SearchBucket.strong_down: 0,
    SearchBucket.down: 1,
    SearchBucket.flat: 2,
    SearchBucket.up: 3,
    SearchBucket.strong_up: 4,
}


@dataclass
class StabilityBagResult:
    slug: str
    weeks: int
    flip_rate: float
    flip_pass: bool
    reproducibility_trials: int
    reproducibility_share: float
    reproducibility_pass: bool
    alias_share: float
    alias_pass: bool
    window_share: float
    window_pass: bool


@dataclass
class StabilityDecision:
    recommended_search_weight: int
    rationale: str
    bags_failing_flip: int
    per_bag: list[StabilityBagResult]


def evaluate_bag(session: Session, bag_id: int, slug: str) -> StabilityBagResult:
    signals = session.scalars(
        select(SearchSignalWeekly)
        .where(SearchSignalWeekly.bag_model_id == bag_id)
        .order_by(SearchSignalWeekly.week_start)
    ).all()

    flip_rate, flip_pass = _flip_rate(signals)
    alias_share, alias_pass = _alias_agreement(signals)
    window_share, window_pass = _window_robustness(signals)

    pulls = session.scalars(
        select(TrendPull)
        .where(TrendPull.bag_model_id == bag_id, TrendPull.query_role == TrendQueryRole.canonical)
        .order_by(TrendPull.window_start, TrendPull.window_end)
    ).all()
    trials, repro_share, repro_pass = _reproducibility(pulls)

    return StabilityBagResult(
        slug=slug,
        weeks=len(signals),
        flip_rate=round(flip_rate, 4),
        flip_pass=flip_pass,
        reproducibility_trials=trials,
        reproducibility_share=round(repro_share, 4),
        reproducibility_pass=repro_pass,
        alias_share=round(alias_share, 4),
        alias_pass=alias_pass,
        window_share=round(window_share, 4),
        window_pass=window_pass,
    )


def run_stability(session: Session) -> StabilityDecision:
    bags = session.scalars(select(BagModel).order_by(BagModel.slug)).all()
    per_bag = [evaluate_bag(session, bag.id, bag.slug) for bag in bags]
    return _decide(per_bag)


def _flip_rate(signals: list[SearchSignalWeekly]) -> tuple[float, bool]:
    if len(signals) < 2:
        return 0.0, True
    slopes = [float(s.slope_8w) if s.slope_8w is not None else 0.0 for s in signals]
    counted_flips = 0
    transitions = 0
    for i in range(1, len(signals)):
        transitions += 1
        if signals[i].bucket == signals[i - 1].bucket:
            continue
        trailing = slopes[:i]
        exemption = STABILITY_SLOPE_CHANGE_EXEMPTION * stdev(trailing)
        slope_move = abs(slopes[i] - slopes[i - 1])
        if exemption > 0 and slope_move > exemption:
            # Real underlying move is allowed to flip the bucket; not noise.
            continue
        counted_flips += 1
    rate = counted_flips / transitions if transitions else 0.0
    return rate, rate < STABILITY_FLIP_RATE_MAX


def _alias_agreement(signals: list[SearchSignalWeekly]) -> tuple[float, bool]:
    checked = [s for s in signals if s.alias_agrees is not None]
    if not checked:
        return 1.0, True
    agree = sum(1 for s in checked if s.alias_agrees)
    share = agree / len(checked)
    return share, share >= STABILITY_ALIAS_AGREEMENT_MIN


def _window_robustness(signals: list[SearchSignalWeekly]) -> tuple[float, bool]:
    checks = 0
    agree = 0
    for s in signals:
        if s.slope_8w is None or s.slope_4w is None:
            continue
        checks += 1
        if _sign(float(s.slope_8w)) == _sign(float(s.slope_4w)):
            agree += 1
    if checks == 0:
        return 1.0, True
    share = agree / checks
    return share, share >= STABILITY_WINDOW_ROBUSTNESS_MIN


def _reproducibility(pulls: list[TrendPull]) -> tuple[int, float, bool]:
    if not pulls:
        return 0, 0.0, False
    groups: dict[tuple[date, date], list[TrendPull]] = {}
    for pull in pulls:
        groups.setdefault((pull.window_start, pull.window_end), []).append(pull)
    window, trials_pulls = max(groups.items(), key=lambda kv: len(kv[1]))
    buckets = [_pull_bucket(pull) for pull in trials_pulls]
    trials = len(buckets)
    reference = Counter(buckets).most_common(1)[0][0]
    ref_ord = _BUCKET_ORDINAL[reference]
    within_one = sum(1 for b in buckets if abs(_BUCKET_ORDINAL[b] - ref_ord) <= 1)
    share = within_one / trials
    passed = trials >= STABILITY_REPRODUCIBILITY_MIN_TRIALS and share >= STABILITY_REPRODUCIBILITY_MIN_SHARE
    return trials, share, passed


def _pull_bucket(pull: TrendPull) -> SearchBucket:
    values = [float(p["value"]) for p in (pull.weekly_points or [])]
    window = values[-8:] if len(values) >= 8 else values
    return bucket_for_slope(linear_slope(window))


def _sign(value: float) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _decide(per_bag: list[StabilityBagResult]) -> StabilityDecision:
    bags_failing_flip = sum(1 for r in per_bag if not r.flip_pass)
    passing_flip = len(per_bag) - bags_failing_flip

    if bags_failing_flip >= 3:
        return StabilityDecision(
            recommended_search_weight=0,
            rationale=f"S excluded: per-bag stability failed on {bags_failing_flip} bags (>=3).",
            bags_failing_flip=bags_failing_flip,
            per_bag=per_bag,
        )
    if bags_failing_flip >= 2:
        return StabilityDecision(
            recommended_search_weight=SEARCH_WEIGHT_DEMOTED,
            rationale=f"S demoted to {SEARCH_WEIGHT_DEMOTED}%: per-bag stability failed on 2 bags.",
            bags_failing_flip=bags_failing_flip,
            per_bag=per_bag,
        )

    other_tests_pass = all(r.reproducibility_pass and r.alias_pass and r.window_pass for r in per_bag)
    if passing_flip >= STABILITY_BAGS_REQUIRED and other_tests_pass:
        return StabilityDecision(
            recommended_search_weight=SEARCH_WEIGHT_FULL,
            rationale=(
                f"S may rise to {SEARCH_WEIGHT_FULL}%: all four stability tests pass "
                f"(per-bag stability on {passing_flip}/{len(per_bag)} bags)."
            ),
            bags_failing_flip=bags_failing_flip,
            per_bag=per_bag,
        )
    return StabilityDecision(
        recommended_search_weight=SEARCH_WEIGHT_BASE,
        rationale=(
            f"S stays at {SEARCH_WEIGHT_BASE}% (flagged): per-bag stability holds but "
            "reproducibility/alias/window tests did not all pass."
        ),
        bags_failing_flip=bags_failing_flip,
        per_bag=per_bag,
    )
