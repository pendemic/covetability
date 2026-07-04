from __future__ import annotations

from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal

from app.contract import WINSOR_PCT

CENT = Decimal("0.01")
CONFIDENCE_QUANT = Decimal("0.0001")


def percentile(values: list[Decimal] | tuple[Decimal, ...], pct: int) -> Decimal:
    if not values:
        raise ValueError("percentile requires at least one value")
    if pct < 0 or pct > 100:
        raise ValueError("percentile must be between 0 and 100")

    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]

    rank = (Decimal(len(sorted_values) - 1) * Decimal(pct)) / Decimal(100)
    lower_index = int(rank.to_integral_value(rounding=ROUND_FLOOR))
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = rank - Decimal(lower_index)
    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]
    return lower + ((upper - lower) * fraction)


def winsorize(values: list[Decimal] | tuple[Decimal, ...]) -> list[Decimal]:
    if not values:
        return []
    low_pct, high_pct = WINSOR_PCT
    lower = percentile(values, low_pct)
    upper = percentile(values, high_pct)
    return [min(max(value, lower), upper) for value in values]


def median(values: list[Decimal] | tuple[Decimal, ...]) -> Decimal:
    return percentile(values, 50)


def quantize_price(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def quantize_confidence(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(CONFIDENCE_QUANT, rounding=ROUND_HALF_UP)


def price_summary(values: list[Decimal]) -> tuple[Decimal, Decimal, Decimal]:
    clipped = winsorize(values)
    return (
        quantize_price(percentile(clipped, 50)),
        quantize_price(percentile(clipped, 25)),
        quantize_price(percentile(clipped, 75)),
    )
