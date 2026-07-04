from decimal import Decimal

from app.aggregates.stats import median, percentile, price_summary, quantize_confidence, winsorize


def test_percentile_interpolates_with_decimals() -> None:
    values = [Decimal("10"), Decimal("20")]

    assert percentile(values, 25) == Decimal("12.5")
    assert median(values) == Decimal("15")


def test_winsorized_price_summary_is_cent_quantized() -> None:
    values = [
        Decimal("100"),
        Decimal("110"),
        Decimal("120"),
        Decimal("130"),
        Decimal("140"),
        Decimal("150"),
        Decimal("160"),
        Decimal("170"),
        Decimal("180"),
        Decimal("9999"),
    ]

    clipped = winsorize(values)
    median_price, p25, p75 = price_summary(values)

    assert clipped[-1] < Decimal("9999")
    assert p25 <= median_price <= p75
    assert median_price == Decimal("145.00")


def test_quantize_confidence_uses_four_places() -> None:
    assert quantize_confidence(Decimal("0.912345")) == Decimal("0.9123")
