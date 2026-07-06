"""Shared numeric helpers for score v0 components (Phase 5).

Kept dependency-light on purpose: components map raw signals to a 0-100 scale
through provisional ladders, and the ladders/slope math live here so the
component calculators read declaratively.
"""

from __future__ import annotations

from collections.abc import Sequence


def map_ladder(
    value: float,
    ladder: Sequence[tuple[float, int]],
    *,
    floor_score: int = 0,
) -> int:
    """Return the first ladder score whose threshold ``value`` clears.

    ``ladder`` is ordered high threshold -> low threshold. If ``value`` clears
    none of the thresholds it falls through to ``floor_score``.
    """

    for threshold, score in ladder:
        if value >= threshold:
            return score
    return floor_score


def linear_slope(values: Sequence[float]) -> float:
    """Least-squares slope over evenly spaced points (x = 0, 1, ... n-1).

    Returns 0.0 for fewer than two points. Units are "signal per step".
    """

    n = len(values)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2
    mean_y = sum(values) / n
    numerator = sum((i - mean_x) * (y - mean_y) for i, y in enumerate(values))
    denominator = sum((i - mean_x) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0
    return numerator / denominator


def pct_change(old: float, new: float) -> float:
    """Fractional change from ``old`` to ``new``.

    Returns 0.0 when the baseline is zero (no defined momentum).
    """

    if old == 0:
        return 0.0
    return (new - old) / old


def stdev(values: Sequence[float]) -> float:
    """Population standard deviation; 0.0 for fewer than two points."""

    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    return variance**0.5
