"""Eligibility gating and weight redistribution (score-spec §4).

Pure functions: given which components are eligible, produce the redistributed
weights. Freed weight from excluded components is spread pro-rata among the
eligible ones respecting each ceiling; weight that still cannot be placed goes
to inventory first, then breadth (the designated sinks). Breadth is never gated
in practice, so a sink is always available. P's ceiling is a hard circularity
cap and is never used as a sink, so P can never exceed 25.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.contract import (
    COMPONENT_KEYS,
    COMPONENT_PRICE,
    MIN_ELIGIBLE_COMPONENTS,
    REDISTRIBUTION_OVERFLOW_ORDER,
    SCORE_BASE_WEIGHTS,
    SCORE_WEIGHT_CEILINGS,
)

_EPS = 1e-9


@dataclass
class RedistributionResult:
    scored: bool
    weights: dict[str, float]
    eligible: list[str]
    overflow_to: str | None
    unscored_reason: str | None


def redistribute(
    eligibility: dict[str, bool],
    *,
    weight_overrides: dict[str, int] | None = None,
) -> RedistributionResult:
    base = dict(SCORE_BASE_WEIGHTS)
    if weight_overrides:
        base.update(weight_overrides)

    eligible = [key for key in COMPONENT_KEYS if eligibility.get(key)]
    weights = {key: 0.0 for key in COMPONENT_KEYS}

    if len(eligible) < MIN_ELIGIBLE_COMPONENTS:
        return RedistributionResult(
            scored=False,
            weights=weights,
            eligible=eligible,
            overflow_to=None,
            unscored_reason=f"only {len(eligible)} eligible components (need {MIN_ELIGIBLE_COMPONENTS})",
        )

    pool = float(sum(base[key] for key in COMPONENT_KEYS if key not in eligible))
    for key in eligible:
        weights[key] = float(base[key])

    pool = _fill_pro_rata(weights, eligible, base, pool)

    overflow_to: str | None = None
    if pool > _EPS:
        overflow_to = _pick_sink(eligible)
        weights[overflow_to] += pool
        pool = 0.0

    _round_to_hundred(weights, eligible, overflow_to)
    return RedistributionResult(
        scored=True,
        weights=weights,
        eligible=eligible,
        overflow_to=overflow_to,
        unscored_reason=None,
    )


def _fill_pro_rata(
    weights: dict[str, float],
    eligible: list[str],
    base: dict[str, int],
    pool: float,
) -> float:
    while pool > _EPS:
        headroom = [k for k in eligible if weights[k] < SCORE_WEIGHT_CEILINGS[k] - _EPS]
        if not headroom:
            break
        total_base = sum(base[k] for k in headroom)
        added = 0.0
        for key in headroom:
            share = pool * base[key] / total_base
            room = SCORE_WEIGHT_CEILINGS[key] - weights[key]
            grant = min(share, room)
            weights[key] += grant
            added += grant
        if added <= _EPS:
            break
        pool -= added
    return pool


def _pick_sink(eligible: list[str]) -> str:
    for sink in REDISTRIBUTION_OVERFLOW_ORDER:
        if sink in eligible:
            return sink
    # Fallback (does not occur while breadth is never gated): any eligible
    # non-price component, so P's hard cap is preserved.
    for key in eligible:
        if key != COMPONENT_PRICE:
            return key
    return eligible[0]


def _round_to_hundred(weights: dict[str, float], eligible: list[str], sink: str | None) -> None:
    for key in weights:
        weights[key] = round(weights[key], 2)
    residual = round(100.0 - sum(weights.values()), 2)
    if abs(residual) < _EPS:
        return
    target = sink or (eligible[0] if eligible else None)
    if target is not None:
        weights[target] = round(weights[target] + residual, 2)
