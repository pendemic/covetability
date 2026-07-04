from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.contract import ConditionBand, GoldLabelOrigin, GoldLabelVerdict, RejectionReason
from app.db import SessionLocal
from app.models import BagModel, BagVariant, GoldLabel, ListingRaw
from app.settings import get_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load fixture expected labels into gold_labels.")
    parser.add_argument("--path", help="Expected-label JSON path.")
    return parser.parse_args()


def default_path() -> Path:
    return get_settings().package_root / "fixtures" / "ebay" / "expected_labels.json"


def main() -> int:
    args = parse_args()
    path = Path(args.path) if args.path else default_path()
    labels = json.loads(path.read_text(encoding="utf-8"))

    with SessionLocal() as session:
        bag_by_slug = {bag.slug: bag for bag in session.scalars(select(BagModel)).all()}
        variants_by_bag = {
            bag.slug: {variant.name: variant for variant in bag.variants}
            for bag in session.scalars(select(BagModel)).all()
        }
        listings_by_item = {
            listing.marketplace_item_id: listing for listing in session.scalars(select(ListingRaw)).all()
        }
        loaded = 0
        for label in labels:
            upsert_label(session, label, bag_by_slug, variants_by_bag, listings_by_item)
            loaded += 1
        session.commit()

    print(f"loaded fixture gold labels: {loaded}")
    return 0


def upsert_label(
    session,
    label: dict[str, Any],
    bag_by_slug: dict[str, BagModel],
    variants_by_bag: dict[str, dict[str, BagVariant]],
    listings_by_item: dict[str, ListingRaw],
) -> None:
    bag = bag_by_slug[label["bag_slug"]]
    verdict = GoldLabelVerdict(label["verdict"])
    variant_name = label.get("variant")
    variant = variants_by_bag[label["bag_slug"]].get(variant_name) if variant_name else None
    rejection_reason = (
        RejectionReason(label["rejection_reason"])
        if verdict == GoldLabelVerdict.reject
        else None
    )
    listing = listings_by_item.get(label["item_id"])
    values = {
        "listing_id": listing.id if listing is not None else None,
        "marketplace_item_id": label["item_id"],
        "bag_model_id": bag.id,
        "verdict": verdict,
        "origin": GoldLabelOrigin.fixture_seed,
        "rejection_reason": rejection_reason,
        "accepted_variant_id": variant.id if variant is not None else None,
        "color_family": label.get("color_family"),
        "condition_band": (
            ConditionBand(label["condition_band"]) if label.get("condition_band") else None
        ),
        "strap_included": label.get("strap_included"),
        "lock_included": label.get("lock_included"),
        "key_included": label.get("key_included"),
        "dustbag_included": label.get("dustbag_included"),
        "cards_included": label.get("cards_included"),
        "labeled_by": "fixture",
        "labeled_at": datetime.now(UTC),
        "notes": label.get("note"),
    }
    statement = (
        insert(GoldLabel)
        .values(**values)
        .on_conflict_do_update(
            constraint="uq_gold_labels_item_bag",
            set_=values,
        )
    )
    session.execute(statement)


if __name__ == "__main__":
    raise SystemExit(main())
