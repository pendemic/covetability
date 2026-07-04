from __future__ import annotations

import argparse

from sqlalchemy import func, select

from app.conditions.normalize import CONDITION_NORMALIZER_VERSION, normalize_condition
from app.db import SessionLocal
from app.models import BagModel, ListingRaw


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize listing condition bands.")
    parser.add_argument("--all", action="store_true", help="Normalize every listing.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with SessionLocal() as session:
        bag_slug_by_id = {bag.id: bag.slug for bag in session.scalars(select(BagModel)).all()}
        query = select(ListingRaw).order_by(ListingRaw.id)
        if not args.all:
            query = query.where(
                ListingRaw.condition_normalizer_version.is_distinct_from(CONDITION_NORMALIZER_VERSION)
            )
        listings = session.scalars(query).all()
        for listing in listings:
            assessment = normalize_condition(
                listing.condition_raw,
                listing.title,
                bag_slug=bag_slug_by_id.get(listing.candidate_bag_model_id),
            )
            listing.condition_band = assessment.band
            listing.condition_confidence = assessment.confidence
            listing.condition_normalizer_version = CONDITION_NORMALIZER_VERSION
        session.commit()

        distribution = session.execute(
            select(ListingRaw.condition_band, ListingRaw.condition_confidence, func.count())
            .group_by(ListingRaw.condition_band, ListingRaw.condition_confidence)
            .order_by(ListingRaw.condition_band, ListingRaw.condition_confidence)
        ).all()

    print(f"normalized conditions: {len(listings)}")
    print("band,confidence,count")
    for band, confidence, count in distribution:
        print(
            f"{band.value if band else 'unbanded'},"
            f"{confidence.value if confidence else 'indeterminate'},"
            f"{count}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
