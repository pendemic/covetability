from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, selectinload

from app.contract import GoldLabelOrigin, GoldLabelVerdict, MatchStatus, RejectionReason
from app.ingestion.fixtures import FixtureSource
from app.ingestion.snapshot import run_snapshot
from app.matching.engine import apply_matching
from app.matching.evaluate import evaluate_matcher
from app.matching.matcher import CatalogIndex, MatchResult
from app.models import BagModel, GoldLabel, ListingRaw, MatchRun, SnapshotRun
from seeds.catalog import seed

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "ebay"


def cleanup_fixture_rows(engine: Engine) -> None:
    with Session(engine) as session:
        session.execute(delete(GoldLabel).where(GoldLabel.marketplace_item_id.like("v1|fx%")))
        session.execute(delete(MatchRun))
        session.execute(delete(SnapshotRun))
        session.execute(delete(ListingRaw).where(ListingRaw.marketplace_item_id.like("v1|fx%")))
        session.commit()


def seed_and_snapshot(engine: Engine) -> None:
    cleanup_fixture_rows(engine)
    with Session(engine) as session:
        seed(session)
        run_snapshot(
            session,
            FixtureSource(FIXTURES_DIR),
            as_of=datetime(2026, 7, 2, 12, tzinfo=UTC),
        )
        session.commit()


def load_expected_gold(session: Session) -> None:
    labels = json.loads((FIXTURES_DIR / "expected_labels.json").read_text(encoding="utf-8"))
    bags = session.scalars(
        select(BagModel).options(selectinload(BagModel.variants)).order_by(BagModel.slug)
    ).all()
    bag_by_slug = {bag.slug: bag for bag in bags}
    variant_by_bag = {bag.slug: {variant.name: variant for variant in bag.variants} for bag in bags}
    listing_by_item = {
        listing.marketplace_item_id: listing
        for listing in session.scalars(select(ListingRaw).order_by(ListingRaw.id)).all()
    }

    for label in labels:
        bag = bag_by_slug[label["bag_slug"]]
        variant = variant_by_bag[label["bag_slug"]].get(label["variant"])
        verdict = GoldLabelVerdict(label["verdict"])
        session.add(
            GoldLabel(
                listing_id=listing_by_item[label["item_id"]].id,
                marketplace_item_id=label["item_id"],
                bag_model_id=bag.id,
                verdict=verdict,
                origin=GoldLabelOrigin.fixture_seed,
                rejection_reason=(
                    RejectionReason(label["rejection_reason"])
                    if verdict == GoldLabelVerdict.reject
                    else None
                ),
                accepted_variant_id=variant.id if variant is not None else None,
                color_family=label["color_family"],
                labeled_by="fixture",
                notes=label["note"],
            )
        )


def test_catalog_index_from_session_matches_seed_catalog(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        seed(session)
        session.commit()

        from_session = CatalogIndex.from_session(session)
        from_seed = CatalogIndex.from_seed()

    assert set(from_session.bags) == set(from_seed.bags)
    for slug in from_seed.bags:
        assert set(from_session.bags[slug].aliases) == set(from_seed.bags[slug].aliases)
        assert {variant.name for variant in from_session.bags[slug].variants} == {
            variant.name for variant in from_seed.bags[slug].variants
        }
        assert {row.term for row in from_session.bags[slug].exclusions} == {
            row.term for row in from_seed.bags[slug].exclusions
        }


def test_apply_matching_writes_statuses_and_is_incrementally_idempotent(db_engine: Engine) -> None:
    seed_and_snapshot(db_engine)
    with Session(db_engine) as session:
        summary = apply_matching(session)
        session.commit()

        pending = session.scalar(
            select(func.count()).select_from(ListingRaw).where(ListingRaw.match_status == MatchStatus.pending)
        )
        run_count = session.scalar(select(func.count()).select_from(MatchRun))
        accepted = session.scalar(
            select(func.count()).select_from(ListingRaw).where(
                ListingRaw.match_status == MatchStatus.auto_accepted
            )
        )

        assert summary.listings_considered == 140
        assert pending == 0
        assert accepted and accepted > 0
        assert run_count == 1

        second = apply_matching(session)
        session.commit()

        assert second.listings_considered == 0
        assert session.scalar(select(func.count()).select_from(MatchRun)) == 2

    cleanup_fixture_rows(db_engine)


def test_full_rematch_pins_human_rows_and_logs_large_delta(db_engine: Engine, monkeypatch) -> None:
    seed_and_snapshot(db_engine)
    with Session(db_engine) as session:
        apply_matching(session)
        listing = session.scalar(
            select(ListingRaw).where(ListingRaw.marketplace_item_id == "v1|fx-chloe-paddington-001|0")
        )
        assert listing is not None
        listing.match_status = MatchStatus.human_rejected
        listing.matched_bag_model_id = None
        listing.matched_variant_id = None
        listing.matcher_version = "manual"
        session.commit()

        def reject_all(title, index, *, candidate_bag_slug=None):  # noqa: ARG001
            return MatchResult(
                bag_slug=None,
                variant_name=None,
                confidence=0.0,
                status=MatchStatus.auto_rejected,
                trace={"matcher_version": "test", "candidates": [], "selected": None},
            )

        monkeypatch.setattr("app.matching.engine.match_listing", reject_all)
        summary = apply_matching(session, only_pending=False)
        session.commit()

        session.refresh(listing)
        assert listing.match_status == MatchStatus.human_rejected
        assert listing.matcher_version == "manual"
        assert summary.threshold_exceeded
        assert session.scalars(select(MatchRun).order_by(MatchRun.id)).all()[-1].threshold_exceeded

    cleanup_fixture_rows(db_engine)


def test_fixture_gold_evaluation_passes_contract_targets(db_engine: Engine) -> None:
    seed_and_snapshot(db_engine)
    with Session(db_engine) as session:
        load_expected_gold(session)
        session.commit()

        report = evaluate_matcher(session, gold_origin=GoldLabelOrigin.fixture_seed.value)

        assert report.total_labels == 140
        assert report.unevaluable_labels == 0
        assert report.passes_targets
        assert report.false_positive == 0
        assert report.variant_attribution == 1.0

    cleanup_fixture_rows(db_engine)
