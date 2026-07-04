from __future__ import annotations

from dataclasses import dataclass

from app.conditions.keywords import (
    GLOBAL_DAMAGE_TERMS,
    GLOBAL_POSITIVE_TERMS,
    PER_BAG_CONDITION_TERMS,
    STRUCTURED_CONDITION_MAP,
    UNSTRUCTURED_CONDITIONS,
)
from app.contract import ConditionBand, ConditionConfidence
from app.matching.normalize import contains_term, normalize_text

CONDITION_NORMALIZER_VERSION = "1.0"
CONDITION_SCALE = tuple(ConditionBand)


@dataclass(frozen=True)
class ConditionSignal:
    term: str
    band: ConditionBand
    source: str


@dataclass(frozen=True)
class ConditionAssessment:
    band: ConditionBand | None
    confidence: ConditionConfidence
    signals: tuple[ConditionSignal, ...]


def normalize_condition(
    condition_raw: str | None,
    title: str,
    *,
    description: str | None = None,
    bag_slug: str | None = None,
) -> ConditionAssessment:
    structured = structured_band(condition_raw)
    evidence = normalize_text(" ".join(value for value in (title, description or "") if value))
    damage = scan_damage_terms(evidence, bag_slug)
    positives = scan_positive_terms(evidence)

    if structured is not None:
        if damage:
            cap = lowest_band(signal.band for signal in damage)
            if band_rank(structured) < band_rank(cap):
                return ConditionAssessment(cap, ConditionConfidence.medium, tuple(damage))
        return ConditionAssessment(structured, ConditionConfidence.high, tuple(damage))

    if positives:
        band = positives[0].band
        confidence = ConditionConfidence.medium if len(positives) >= 2 else ConditionConfidence.low
        return ConditionAssessment(band, confidence, tuple(positives))

    if damage:
        return ConditionAssessment(
            lowest_band(signal.band for signal in damage),
            ConditionConfidence.low,
            tuple(damage),
        )

    return ConditionAssessment(None, ConditionConfidence.indeterminate, ())


def structured_band(condition_raw: str | None) -> ConditionBand | None:
    if condition_raw is None:
        return None
    normalized = normalize_text(condition_raw.replace("-", " "))
    if normalized in UNSTRUCTURED_CONDITIONS:
        return None
    return STRUCTURED_CONDITION_MAP.get(normalized)


def scan_damage_terms(text: str, bag_slug: str | None) -> list[ConditionSignal]:
    signals: list[ConditionSignal] = []
    for term, cap in GLOBAL_DAMAGE_TERMS:
        if contains_term(text, term):
            signals.append(ConditionSignal(term=term, band=cap, source="global_damage"))
    for term, cap in PER_BAG_CONDITION_TERMS.get(bag_slug or "", ()):
        if contains_term(text, term):
            signals.append(ConditionSignal(term=term, band=cap, source="bag_damage"))
    return signals


def scan_positive_terms(text: str) -> list[ConditionSignal]:
    return [
        ConditionSignal(term=term, band=band, source="positive")
        for term, band in GLOBAL_POSITIVE_TERMS
        if contains_term(text, term)
    ]


def lowest_band(bands: list[ConditionBand] | tuple[ConditionBand, ...]) -> ConditionBand:
    return max(bands, key=band_rank)


def band_rank(band: ConditionBand) -> int:
    return CONDITION_SCALE.index(band)


def band_distance(left: ConditionBand, right: ConditionBand) -> int:
    return abs(band_rank(left) - band_rank(right))
