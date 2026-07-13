"""Generate a continuous multi-day daily_aggregates history for the pilot bags.

The fixture snapshot drops a fresh single-date cohort each run, so day-over-day
analysis (observation deltas, 30/90-day score windows, momentum) has no signal.
This job lays down a smooth, drifting per-band history — model-level plus the
separate-market colorway variants — so the cross-day engines have real trends to
read. It replaces any existing pilot aggregates in the window (clearing the
accumulated single-date artifact days).

    uv run python -m jobs.seed_history --days 120        # ending at latest snapshot day
    uv run python -m jobs.seed_history --days 120 --end 2026-07-09
"""

from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import delete, func, select, update

from app.contract import ConditionBand, SearchBucket
from app.db import get_session
from app.models import BagModel, DailyAggregate, ListingRaw, SearchSignalWeekly


@dataclass
class BandProfile:
    band: ConditionBand
    base_median: float  # oldest-day median asking
    base_active: int


@dataclass
class VariantProfile:
    variant_id: int
    price_mult: float
    active_mult: float
    bands: tuple[ConditionBand, ...]


@dataclass
class BagProfile:
    slug: str
    price_trend: float  # fractional change oldest -> newest (e.g. +0.14)
    active_trend: float
    bands: list[BandProfile]
    variants: list[VariantProfile] = field(default_factory=list)


B = ConditionBand

PROFILES: list[BagProfile] = [
    BagProfile(
        slug="chloe-paddington",
        price_trend=0.14,
        active_trend=0.55,
        bands=[
            BandProfile(B.new_or_unused, 1500, 6),
            BandProfile(B.excellent, 1100, 14),
            BandProfile(B.very_good, 850, 18),
            BandProfile(B.good, 600, 12),
            BandProfile(B.fair, 460, 7),
        ],
    ),
    BagProfile(
        slug="balenciaga-city",
        price_trend=0.07,
        active_trend=0.20,
        bands=[
            BandProfile(B.excellent, 920, 10),
            BandProfile(B.very_good, 720, 16),
            BandProfile(B.good, 540, 14),
            BandProfile(B.fair, 400, 8),
            BandProfile(B.poor, 290, 5),
        ],
        variants=[VariantProfile(10, 0.75, 0.30, (B.excellent, B.very_good, B.good))],
    ),
    BagProfile(
        slug="dior-saddle",
        price_trend=0.18,
        active_trend=0.40,
        bands=[
            BandProfile(B.new_or_unused, 1750, 5),
            BandProfile(B.excellent, 1350, 12),
            BandProfile(B.very_good, 1000, 16),
            BandProfile(B.good, 760, 11),
            BandProfile(B.fair, 540, 6),
            BandProfile(B.poor, 400, 4),
        ],
        variants=[
            VariantProfile(17, 1.15, 0.45, (B.excellent, B.very_good, B.good, B.fair)),
            VariantProfile(18, 0.85, 0.35, (B.excellent, B.very_good, B.good)),
        ],
    ),
    BagProfile(
        slug="fendi-baguette",
        price_trend=0.04,
        active_trend=0.10,
        bands=[
            BandProfile(B.new_or_unused, 2000, 5),
            BandProfile(B.excellent, 1350, 10),
            BandProfile(B.very_good, 950, 13),
            BandProfile(B.good, 620, 8),
        ],
        variants=[VariantProfile(16, 0.70, 0.30, (B.excellent, B.very_good, B.good))],
    ),
    BagProfile(
        slug="louis-vuitton-pochette-accessoires",
        price_trend=-0.06,
        active_trend=-0.12,
        bands=[
            BandProfile(B.new_or_unused, 700, 7),
            BandProfile(B.excellent, 560, 15),
            BandProfile(B.very_good, 470, 20),
            BandProfile(B.good, 410, 14),
            BandProfile(B.fair, 360, 9),
            BandProfile(B.poor, 300, 5),
        ],
        variants=[VariantProfile(23, 1.10, 0.25, (B.excellent, B.very_good, B.good))],
    ),
    # --- Extended catalog (model-level history only; no separate-market variants) ---
    BagProfile("chanel-25", 0.10, 0.30, [
        BandProfile(B.new_or_unused, 6800, 5), BandProfile(B.excellent, 5200, 9),
        BandProfile(B.very_good, 4300, 11), BandProfile(B.good, 3600, 7),
    ]),
    BagProfile("dior-gaucho", 0.20, 0.50, [
        BandProfile(B.excellent, 1100, 6), BandProfile(B.very_good, 820, 10),
        BandProfile(B.good, 560, 8), BandProfile(B.fair, 380, 5),
    ]),
    BagProfile("dior-columbus", 0.05, 0.08, [
        BandProfile(B.very_good, 460, 6), BandProfile(B.good, 340, 8), BandProfile(B.fair, 260, 5),
    ]),
    BagProfile("ysl-mombasa", 0.12, 0.28, [
        BandProfile(B.new_or_unused, 1900, 4), BandProfile(B.excellent, 1450, 8),
        BandProfile(B.very_good, 1100, 10), BandProfile(B.good, 820, 7),
    ]),
    BagProfile("miu-miu-vitello", -0.03, -0.06, [
        BandProfile(B.excellent, 620, 8), BandProfile(B.very_good, 480, 12),
        BandProfile(B.good, 360, 9), BandProfile(B.fair, 260, 6),
    ]),
    BagProfile("chloe-silverado", 0.08, 0.18, [
        BandProfile(B.excellent, 780, 7), BandProfile(B.very_good, 600, 11),
        BandProfile(B.good, 440, 8), BandProfile(B.fair, 320, 5),
    ]),
    BagProfile("gucci-indy", -0.05, -0.10, [
        BandProfile(B.excellent, 720, 6), BandProfile(B.very_good, 560, 9), BandProfile(B.good, 420, 7),
    ]),
    BagProfile("prada-bonnie", 0.02, 0.05, [
        BandProfile(B.very_good, 520, 7), BandProfile(B.good, 400, 9), BandProfile(B.fair, 300, 5),
    ]),
    BagProfile("louis-vuitton-pochette", 0.16, 0.60, [
        BandProfile(B.excellent, 520, 12), BandProfile(B.very_good, 420, 18),
        BandProfile(B.good, 340, 14), BandProfile(B.fair, 260, 8), BandProfile(B.poor, 190, 5),
    ]),
    BagProfile("fendi-spy", 0.09, 0.20, [
        BandProfile(B.new_or_unused, 1600, 5), BandProfile(B.excellent, 1200, 9),
        BandProfile(B.very_good, 900, 12), BandProfile(B.good, 640, 8), BandProfile(B.fair, 460, 5),
    ]),
    BagProfile("gucci-jackie", 0.11, 0.25, [
        BandProfile(B.new_or_unused, 1500, 5), BandProfile(B.excellent, 1150, 9),
        BandProfile(B.very_good, 880, 11), BandProfile(B.good, 640, 7),
    ]),
    BagProfile("chanel-suede-flap", 0.07, 0.12, [
        BandProfile(B.excellent, 3200, 6), BandProfile(B.very_good, 2500, 9),
        BandProfile(B.good, 1900, 7), BandProfile(B.fair, 1300, 4),
    ]),
    BagProfile("miu-miu-nappa", -0.04, -0.08, [
        BandProfile(B.excellent, 560, 8), BandProfile(B.very_good, 430, 12),
        BandProfile(B.good, 320, 9), BandProfile(B.fair, 230, 6),
    ]),
    BagProfile("miu-miu-pocket", 0.22, 0.70, [
        BandProfile(B.new_or_unused, 1500, 6), BandProfile(B.excellent, 1150, 11),
        BandProfile(B.very_good, 900, 14), BandProfile(B.good, 680, 8),
    ]),
    BagProfile("balenciaga-rodeo", 0.13, 0.35, [
        BandProfile(B.new_or_unused, 2600, 5), BandProfile(B.excellent, 2100, 9),
        BandProfile(B.very_good, 1750, 11), BandProfile(B.good, 1400, 7),
    ]),
    BagProfile("prada-bowling", -0.02, 0.04, [
        BandProfile(B.very_good, 480, 8), BandProfile(B.good, 360, 10),
        BandProfile(B.fair, 260, 6), BandProfile(B.poor, 180, 4),
    ]),
]


def money(value: float) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def build_row(
    *,
    bag_id: int,
    variant_id: int | None,
    band: ConditionBand,
    day: date,
    progress: float,
    base_median: float,
    base_active: int,
    price_trend: float,
    active_trend: float,
    rng: random.Random,
    walk: float,
) -> DailyAggregate:
    # Smooth drift + a gentle seasonal wobble + a bounded random walk shared per series.
    seasonal = 1 + 0.02 * math.sin(progress * math.pi * 3)
    median = base_median * (1 + price_trend * progress) * seasonal * (1 + walk)
    p25 = median * (0.90 - rng.uniform(0, 0.02))
    p75 = median * (1.12 + rng.uniform(0, 0.03))
    active = max(3, round(base_active * (1 + active_trend * progress) + rng.uniform(-1.5, 1.5)))
    matched = max(active, 5)
    ended = max(0, round(active * rng.uniform(0.05, 0.15)))
    new = max(0, round(active * rng.uniform(0.05, 0.18)))
    return DailyAggregate(
        bag_model_id=bag_id,
        variant_id=variant_id,
        condition_band=band,
        observation_date=day,
        active_listing_count=active,
        new_listing_count=new,
        ended_listing_count=ended,
        possible_relist_count=max(0, round(ended * rng.uniform(0, 0.4))),
        median_asking_price=money(median),
        p25_asking_price=money(p25),
        p75_asking_price=money(p75),
        median_total_price=money(median * 1.03),
        source_count=rng.randint(3, 5),
        matched_listing_count=matched,
        average_match_confidence=Decimal(str(round(rng.uniform(0.72, 0.9), 4))),
    )


def generate() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=120, help="Number of continuous days to generate.")
    parser.add_argument("--end", help="End date YYYY-MM-DD (default: latest existing aggregate day, else today).")
    args = parser.parse_args()

    with next(get_session()) as session:
        slugs = [p.slug for p in PROFILES]
        bags = {
            bag.slug: bag
            for bag in session.scalars(select(BagModel).where(BagModel.slug.in_(slugs))).all()
        }
        missing = [slug for slug in slugs if slug not in bags]
        if missing:
            raise SystemExit(f"Missing bags (run seed first): {missing}")

        if args.end:
            end = date.fromisoformat(args.end)
        else:
            end = session.scalar(select(func.max(DailyAggregate.observation_date))) or date.today()
        start = end - timedelta(days=args.days - 1)
        total_days = args.days

        # Clear existing pilot aggregates in the window (removes artifact days).
        bag_ids = [bags[slug].id for slug in slugs]
        session.execute(
            delete(DailyAggregate).where(
                DailyAggregate.bag_model_id.in_(bag_ids),
                DailyAggregate.observation_date >= start,
                DailyAggregate.observation_date <= end,
            )
        )

        inserted = 0
        for profile in PROFILES:
            bag = bags[profile.slug]
            # Independent bounded random walk per (series) for realistic but smooth noise.
            for band_profile in profile.bands:
                rng = random.Random(f"{profile.slug}:{band_profile.band}")
                walk = 0.0
                for offset in range(total_days):
                    day = start + timedelta(days=offset)
                    progress = offset / max(1, total_days - 1)
                    walk = max(-0.06, min(0.06, walk + rng.uniform(-0.012, 0.012)))
                    session.add(
                        build_row(
                            bag_id=bag.id,
                            variant_id=None,
                            band=band_profile.band,
                            day=day,
                            progress=progress,
                            base_median=band_profile.base_median,
                            base_active=band_profile.base_active,
                            price_trend=profile.price_trend,
                            active_trend=profile.active_trend,
                            rng=rng,
                            walk=walk,
                        )
                    )
                    inserted += 1

            base_by_band = {bp.band: bp for bp in profile.bands}
            for variant in profile.variants:
                for band in variant.bands:
                    bp = base_by_band.get(band)
                    if bp is None:
                        continue
                    rng = random.Random(f"{profile.slug}:{variant.variant_id}:{band}")
                    walk = 0.0
                    for offset in range(total_days):
                        day = start + timedelta(days=offset)
                        progress = offset / max(1, total_days - 1)
                        walk = max(-0.06, min(0.06, walk + rng.uniform(-0.012, 0.012)))
                        session.add(
                            build_row(
                                bag_id=bag.id,
                                variant_id=variant.variant_id,
                                band=band,
                                day=day,
                                progress=progress,
                                base_median=bp.base_median * variant.price_mult,
                                base_active=max(3, round(bp.base_active * variant.active_mult)),
                                price_trend=profile.price_trend,
                                active_trend=profile.active_trend,
                                rng=rng,
                                walk=walk,
                            )
                        )
                        inserted += 1

        search_rows = seed_search_signals(session, bags, end)
        bumped = refresh_listing_freshness(session, end)
        session.commit()
        print(
            f"Seeded history {start} .. {end} ({total_days} days) "
            f"rows={inserted} search_weeks={search_rows} listings_refreshed={bumped}"
        )


def refresh_listing_freshness(session, end: date) -> int:
    """Mark matched fixture listings as observed on the seed end date so they stay
    within the active-listings cutoff even as the real calendar advances."""
    observed_at = datetime.combine(end, time(12, 0), tzinfo=UTC)
    result = session.execute(
        update(ListingRaw)
        .where(ListingRaw.matched_bag_model_id.is_not(None))
        .values(last_observed=observed_at)
    )
    return result.rowcount or 0


def bucket_for(trend: float) -> SearchBucket:
    if trend > 0.12:
        return SearchBucket.strong_up
    if trend > 0.03:
        return SearchBucket.up
    if trend > -0.03:
        return SearchBucket.flat
    if trend > -0.12:
        return SearchBucket.down
    return SearchBucket.strong_down


def seed_search_signals(session, bags: dict[str, BagModel], end: date, weeks: int = 24) -> int:
    """Seed a weekly search-interest index per bag so the search component is
    eligible (>=16 weeks, aligned) and the detail-page search chart populates."""
    bag_ids = [bags[profile.slug].id for profile in PROFILES]
    # Anchor the last week to the Monday on/before `end`.
    last_monday = end - timedelta(days=end.weekday())
    session.execute(
        delete(SearchSignalWeekly).where(SearchSignalWeekly.bag_model_id.in_(bag_ids))
    )
    count = 0
    for profile in PROFILES:
        bag = bags[profile.slug]
        trend = profile.price_trend
        rng = random.Random(f"search:{profile.slug}")
        for i in range(weeks):
            week_start = last_monday - timedelta(weeks=weeks - 1 - i)
            progress = i / max(1, weeks - 1)
            value = max(12.0, min(100.0, 45 + trend * 200 * progress + rng.uniform(-1.5, 1.5)))
            session.add(
                SearchSignalWeekly(
                    bag_model_id=bag.id,
                    week_start=week_start,
                    stitched_value=Decimal(str(round(value, 3))),
                    slope_8w=Decimal(str(round(trend, 4))),
                    slope_4w=Decimal(str(round(trend * 1.2, 4))),
                    bucket=bucket_for(trend),
                    alias_agrees=True,
                    low_volume=False,
                    series_length=i + 1,
                )
            )
            count += 1
    return count


if __name__ == "__main__":
    generate()
