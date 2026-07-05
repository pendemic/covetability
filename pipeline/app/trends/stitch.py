"""Overlapping-window stitching with fixed-anchor rescale (score-spec §3).

Google Trends returns each pull on its own in-window 0-100 scale. To build one
continuous multi-month series we rescale each later window onto the scale
established by the overlap with the already-stitched series, then merge.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.trends.source import TrendWindow, WeeklyPoint


@dataclass
class StitchResult:
    points: list[WeeklyPoint]
    rescale_factors: list[float]
    windows_used: int


def stitch_windows(windows: list[TrendWindow]) -> StitchResult:
    """Stitch same-role windows into one weekly series ordered by week.

    Windows are applied oldest-first. Each new window is multiplied by the mean
    ratio of established-to-new values over its overlapping weeks before merging,
    so windows recorded on different in-window scales line up.
    """

    ordered = sorted(windows, key=lambda w: (w.window_start, w.window_end))
    merged: dict[date, float] = {}
    factors: list[float] = []
    used = 0

    for window in ordered:
        if not window.points:
            continue
        used += 1
        window_map = {p.week: p.value for p in window.points}
        if not merged:
            merged.update(window_map)
            factors.append(1.0)
            continue

        factor = _rescale_factor(merged, window_map)
        factors.append(factor)
        for week, value in window_map.items():
            rescaled = value * factor
            # Established weeks keep their value; only genuinely new weeks extend the series.
            merged.setdefault(week, rescaled)

    points = [WeeklyPoint(week=week, value=merged[week]) for week in sorted(merged)]
    return StitchResult(points=points, rescale_factors=factors, windows_used=used)


def _rescale_factor(merged: dict[date, float], window_map: dict[date, float]) -> float:
    ratios: list[float] = []
    for week, value in window_map.items():
        if week in merged and value != 0:
            ratios.append(merged[week] / value)
    if not ratios:
        return 1.0
    return sum(ratios) / len(ratios)
