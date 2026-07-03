from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

TOKEN_RE = re.compile(r"[a-z0-9]+")
MEASUREMENT_RE = re.compile(
    r"(?P<first>\d+(?:\.\d+)?)\s*(?:x|by)\s*(?P<second>\d+(?:\.\d+)?)\s*(?P<unit>cm|in|inch|inches|\")?"
    r"|(?P<single>\d+(?:\.\d+)?)\s*(?P<single_unit>cm|in|inch|inches|\")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NormalizedTitle:
    raw: str
    text: str
    tokens: tuple[str, ...]


@dataclass(frozen=True)
class Measurement:
    value: Decimal
    unit: str


def normalize_text(raw: str) -> str:
    decomposed = unicodedata.normalize("NFKD", raw)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower()
    stripped = re.sub(r"[^a-z0-9]+", " ", lowered)
    return re.sub(r"\s+", " ", stripped).strip()


def normalize_title(raw: str) -> NormalizedTitle:
    text = normalize_text(raw)
    return NormalizedTitle(raw=raw, text=text, tokens=tuple(TOKEN_RE.findall(text)))


def contains_term(normalized_text: str, term: str) -> bool:
    normalized_term = normalize_text(term)
    if not normalized_term:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])"
    return re.search(pattern, normalized_text) is not None


def extract_measurements(raw: str) -> tuple[Measurement, ...]:
    measurements: list[Measurement] = []
    for match in MEASUREMENT_RE.finditer(raw):
        if match.group("first") is not None:
            unit = match.group("unit") or "in"
            measurements.append(Measurement(Decimal(match.group("first")), normalize_unit(unit)))
            measurements.append(Measurement(Decimal(match.group("second")), normalize_unit(unit)))
        elif match.group("single") is not None:
            unit = match.group("single_unit") or "in"
            measurements.append(Measurement(Decimal(match.group("single")), normalize_unit(unit)))
    return tuple(measurements)


def normalize_unit(unit: str) -> str:
    if unit.lower() == "cm":
        return "cm"
    return "in"
