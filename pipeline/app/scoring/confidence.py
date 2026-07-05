"""Confidence function and caps (score-spec §5).

``confidence_raw`` in [0,1] is a weighted blend of matched-listing count,
history length, average match confidence, eligible-component count, and source
count; a set of caps then pulls it down (lowest wins) for thin data.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.contract import (
    CONFIDENCE_CAPS,
    CONFIDENCE_HISTORY_CAP_DAYS,
    CONFIDENCE_HISTORY_FULL_DAYS,
    CONFIDENCE_LOW_MATCHED_LISTINGS,
    CONFIDENCE_MATCHED_LISTING_FULL,
    CONFIDENCE_SOURCE_FULL,
    CONFIDENCE_WEIGHTS,
)


@dataclass
class ConfidenceResult:
    value: float
    raw: float
    caps_applied: list[str]


def compute_confidence(
    *,
    matched_listing_count: int,
    history_days: int,
    average_match_confidence: float,
    eligible_component_count: int,
    source_count: int,
    excluded_component_count: int,
) -> ConfidenceResult:
    raw = (
        CONFIDENCE_WEIGHTS["matched_listing_count"]
        * min(matched_listing_count / CONFIDENCE_MATCHED_LISTING_FULL, 1.0)
        + CONFIDENCE_WEIGHTS["history_length"] * min(history_days / CONFIDENCE_HISTORY_FULL_DAYS, 1.0)
        + CONFIDENCE_WEIGHTS["average_match_confidence"] * max(0.0, min(average_match_confidence, 1.0))
        + CONFIDENCE_WEIGHTS["eligible_component_count"] * min(eligible_component_count / 5, 1.0)
        + CONFIDENCE_WEIGHTS["source_count"] * min(source_count / CONFIDENCE_SOURCE_FULL, 1.0)
    )

    caps: list[tuple[str, float]] = []
    if history_days < CONFIDENCE_HISTORY_CAP_DAYS:
        caps.append(("history_under_90_days", CONFIDENCE_CAPS["history_under_90_days"]))
    if excluded_component_count >= 2:
        caps.append(("two_or_more_components_excluded", CONFIDENCE_CAPS["two_or_more_components_excluded"]))
    elif excluded_component_count >= 1:
        caps.append(("one_component_excluded", CONFIDENCE_CAPS["one_component_excluded"]))
    if matched_listing_count < CONFIDENCE_LOW_MATCHED_LISTINGS:
        caps.append(("model_wide_listings_under_15", CONFIDENCE_CAPS["model_wide_listings_under_15"]))

    value = raw
    applied: list[str] = []
    for name, cap in caps:
        if cap < value:
            value = cap
        applied.append(name)

    return ConfidenceResult(value=round(value, 4), raw=round(raw, 4), caps_applied=applied)
