from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from app.contract import AGGREGATE_WINDOW_DAYS, ConditionBand
from app.models import DailyAggregate


@dataclass(frozen=True)
class Observation:
    metric: str
    window_days: int
    band: ConditionBand | None
    from_value: str | int | None
    to_value: str | int | None
    percent_change: str | None
    magnitude: Decimal
    sentence: str

    def as_dict(self) -> dict[str, str | int | None]:
        return {
            "metric": self.metric,
            "window_days": self.window_days,
            "band": self.band.value if self.band is not None else None,
            "from_value": self.from_value,
            "to_value": self.to_value,
            "percent_change": self.percent_change,
            "magnitude": format_decimal(self.magnitude),
            "sentence": self.sentence,
        }


def generate_observations(rows: list[DailyAggregate], as_of: date) -> list[dict[str, str | int | None]]:
    latest_rows = [row for row in rows if row.observation_date == as_of and row.variant_id is None]
    prior_date = as_of - timedelta(days=AGGREGATE_WINDOW_DAYS)
    prior_by_band = {
        row.condition_band: row
        for row in rows
        if row.observation_date == prior_date and row.variant_id is None
    }

    observations: list[Observation] = []
    for row in latest_rows:
        prior = prior_by_band.get(row.condition_band)
        if (
            prior is None
            or row.median_asking_price is None
            or prior.median_asking_price is None
            or prior.median_asking_price == 0
        ):
            continue
        delta = Decimal(row.median_asking_price) - Decimal(prior.median_asking_price)
        percent = (delta / Decimal(prior.median_asking_price)) * Decimal("100")
        if abs(percent) < Decimal("1"):
            continue
        direction = "up" if percent > 0 else "down"
        observations.append(
            Observation(
                metric="band_median_change",
                window_days=AGGREGATE_WINDOW_DAYS,
                band=row.condition_band,
                from_value=money(prior.median_asking_price),
                to_value=money(row.median_asking_price),
                percent_change=format_decimal(percent),
                magnitude=abs(percent),
                sentence=(
                    f"{band_label(row.condition_band)} median asking moved {direction} "
                    f"{format_decimal(abs(percent))}% over {AGGREGATE_WINDOW_DAYS} days."
                ),
            )
        )

    latest_active = sum(row.active_listing_count for row in latest_rows)
    prior_active = sum(row.active_listing_count for row in prior_by_band.values())
    if prior_by_band and prior_active:
        delta = latest_active - prior_active
        percent = Decimal(delta) / Decimal(prior_active) * Decimal("100")
        if delta:
            direction = "rose" if delta > 0 else "fell"
            observations.append(
                Observation(
                    metric="active_count_change",
                    window_days=AGGREGATE_WINDOW_DAYS,
                    band=None,
                    from_value=prior_active,
                    to_value=latest_active,
                    percent_change=format_decimal(percent),
                    magnitude=abs(percent),
                    sentence=(
                        f"Active matched listings {direction} from {prior_active} to "
                        f"{latest_active} over {AGGREGATE_WINDOW_DAYS} days."
                    ),
                )
            )

    new_count = sum(row.new_listing_count for row in latest_rows)
    if new_count:
        observations.append(
            Observation(
                metric="new_listing_volume",
                window_days=1,
                band=None,
                from_value=None,
                to_value=new_count,
                percent_change=None,
                magnitude=Decimal(new_count),
                sentence=f"{new_count} new matched listings entered tracking on {as_of.isoformat()}.",
            )
        )

    priced_band_count = sum(1 for row in latest_rows if row.median_asking_price is not None)
    if latest_rows:
        observations.append(
            Observation(
                metric="band_coverage",
                window_days=AGGREGATE_WINDOW_DAYS,
                band=None,
                from_value=None,
                to_value=priced_band_count,
                percent_change=None,
                magnitude=Decimal(priced_band_count),
                sentence=(
                    f"{priced_band_count} of 6 condition bands have sufficient listings "
                    "for public asking ranges."
                ),
            )
        )
        observations.append(
            Observation(
                metric="active_inventory",
                window_days=1,
                band=None,
                from_value=None,
                to_value=latest_active,
                percent_change=None,
                magnitude=Decimal(latest_active),
                sentence=f"{latest_active} active matched listings are represented in the latest aggregate.",
            )
        )

    observations.sort(key=lambda item: (item.metric == "band_median_change", item.magnitude), reverse=True)
    return [item.as_dict() for item in observations[:5]]


def band_label(band: ConditionBand) -> str:
    return band.value.replace("_", " ").title()


def money(value: Decimal) -> str:
    return f"{Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}"


def format_decimal(value: Decimal) -> str:
    return str(Decimal(value).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
