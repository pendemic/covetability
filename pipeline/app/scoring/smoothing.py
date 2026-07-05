"""Smoothing, publication threshold, and direction (score-spec §7).

The internal daily raw score is smoothed with a 7-day EMA. The shadow
publication-track value only moves when the smoothed score drifts at least
2 points from the last published value (prevents daily flutter). Direction
arrows come from the 30-day slope of the publication-track series.
"""

from __future__ import annotations

from app.contract import (
    DIRECTION_STABLE_SLOPE,
    PUBLICATION_MOVE_THRESHOLD,
    SCORE_EMA_SPAN_DAYS,
    ScoreDirection,
)
from app.scoring.util import linear_slope


def ema(previous: float | None, raw: float, span: int = SCORE_EMA_SPAN_DAYS) -> float:
    """One EMA step. Seeds with the raw value when there is no prior EMA."""

    if previous is None:
        return round(raw, 2)
    alpha = 2 / (span + 1)
    return round(alpha * raw + (1 - alpha) * previous, 2)


def publication_value(
    previous: float | None,
    smoothed: float,
    *,
    threshold: float = PUBLICATION_MOVE_THRESHOLD,
) -> float:
    """Publication-track value: sticks until the smoothed score moves >= threshold."""

    if previous is None:
        return round(smoothed, 2)
    if abs(smoothed - previous) >= threshold:
        return round(smoothed, 2)
    return round(previous, 2)


def direction(publication_series: list[float]) -> ScoreDirection:
    """Direction from the slope of the trailing publication-track values."""

    if len(publication_series) < 2:
        return ScoreDirection.stable
    slope = linear_slope(publication_series)
    if slope > DIRECTION_STABLE_SLOPE:
        return ScoreDirection.rising
    if slope < -DIRECTION_STABLE_SLOPE:
        return ScoreDirection.falling
    return ScoreDirection.stable
