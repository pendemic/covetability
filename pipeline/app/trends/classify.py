"""Classify the stitched weekly search signal into buckets (score-spec §3, §6).

For each week we compute the 8-week and 4-week least-squares slopes of the
stitched series, map the 8-week slope to one of five buckets, check whether the
canonical and top-alias directions agree, and flag sub-threshold volume.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.contract import (
    SEARCH_LOW_VOLUME_FLOOR,
    SEARCH_SHORT_SLOPE_WEEKS,
    SEARCH_SLOPE_MILD,
    SEARCH_SLOPE_STRONG,
    SEARCH_SMOOTHING_WEEKS,
    SearchBucket,
)
from app.scoring.util import linear_slope
from app.trends.source import WeeklyPoint


@dataclass
class WeeklySignal:
    week_start: date
    stitched_value: float
    slope_8w: float
    slope_4w: float
    bucket: SearchBucket
    alias_agrees: bool | None
    low_volume: bool
    series_length: int
    trace: dict


def bucket_for_slope(slope: float) -> SearchBucket:
    if slope >= SEARCH_SLOPE_STRONG:
        return SearchBucket.strong_up
    if slope >= SEARCH_SLOPE_MILD:
        return SearchBucket.up
    if slope <= -SEARCH_SLOPE_STRONG:
        return SearchBucket.strong_down
    if slope <= -SEARCH_SLOPE_MILD:
        return SearchBucket.down
    return SearchBucket.flat


def _direction(slope: float) -> int:
    if slope >= SEARCH_SLOPE_MILD:
        return 1
    if slope <= -SEARCH_SLOPE_MILD:
        return -1
    return 0


def _trailing_slope(values: list[float], index: int, weeks: int) -> float:
    start = max(0, index - weeks + 1)
    window = values[start : index + 1]
    return linear_slope(window)


def classify_series(
    canonical: list[WeeklyPoint],
    alias: list[WeeklyPoint] | None,
    *,
    low_volume_flag: bool = False,
) -> list[WeeklySignal]:
    canonical_values = [p.value for p in canonical]
    alias_by_week = {p.week: p.value for p in (alias or [])}

    signals: list[WeeklySignal] = []
    for i, point in enumerate(canonical):
        slope_8w = _trailing_slope(canonical_values, i, SEARCH_SMOOTHING_WEEKS)
        slope_4w = _trailing_slope(canonical_values, i, SEARCH_SHORT_SLOPE_WEEKS)
        bucket = bucket_for_slope(slope_8w)

        alias_agrees: bool | None = None
        alias_slope: float | None = None
        if alias:
            aligned = [alias_by_week.get(p.week) for p in canonical[: i + 1]]
            aligned_present = [v for v in aligned if v is not None]
            if len(aligned_present) >= 2:
                alias_slope = _trailing_slope(aligned_present, len(aligned_present) - 1, SEARCH_SMOOTHING_WEEKS)
                alias_agrees = _direction(slope_8w) * _direction(alias_slope) >= 0

        window_start = max(0, i - SEARCH_SMOOTHING_WEEKS + 1)
        window_mean = sum(canonical_values[window_start : i + 1]) / (i - window_start + 1)
        low_volume = low_volume_flag or window_mean < SEARCH_LOW_VOLUME_FLOOR

        signals.append(
            WeeklySignal(
                week_start=point.week,
                stitched_value=point.value,
                slope_8w=slope_8w,
                slope_4w=slope_4w,
                bucket=bucket,
                alias_agrees=alias_agrees,
                low_volume=low_volume,
                series_length=i + 1,
                trace={
                    "slope_8w": round(slope_8w, 4),
                    "slope_4w": round(slope_4w, 4),
                    "alias_slope": round(alias_slope, 4) if alias_slope is not None else None,
                    "window_mean": round(window_mean, 3),
                },
            )
        )
    return signals
