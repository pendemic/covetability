from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.contract import ConditionBand, RejectionReason, VariantKind
from app.main import app
from app.models import BagAlias, BagModel, BagVariant, DailyAggregate, ExclusionTerm
from jobs.recompute_aggregates import clear_recompute_flags
from seeds.catalog import seed
from tests.test_admin_api import auth_headers


def cleanup_catalog_admin_artifacts(engine: Engine) -> None:
    with Session(engine) as session:
        test_variant_ids = select(BagVariant.id).where(BagVariant.name.like("Referenced Variant Test %"))
        session.execute(delete(DailyAggregate).where(DailyAggregate.variant_id.in_(test_variant_ids)))
        session.execute(delete(BagVariant).where(BagVariant.name.like("Referenced Variant Test %")))
        session.execute(delete(BagAlias).where(BagAlias.alias.like("Paddington archive test %")))
        session.execute(delete(ExclusionTerm).where(ExclusionTerm.term.like("phase four global test %")))
        session.commit()


@pytest.fixture(autouse=True)
def clean_catalog_artifacts(db_engine: Engine):
    cleanup_catalog_admin_artifacts(db_engine)
    yield
    cleanup_catalog_admin_artifacts(db_engine)


def reset_flags(session: Session) -> None:
    for bag in session.scalars(select(BagModel)).all():
        bag.recompute_required = False
        bag.recompute_flagged_at = None
    session.commit()


def test_catalog_alias_sets_recompute_flag_and_editorial_patch_does_not(db_engine: Engine) -> None:
    suffix = uuid4().hex
    with Session(db_engine) as session:
        seed(session)
        reset_flags(session)

    with TestClient(app) as client:
        alias_response = client.post(
            "/admin/catalog/bags/chloe-paddington/aliases",
            headers=auth_headers(),
            json={"alias": f"Paddington archive test {suffix}", "type": "alias"},
        )

    assert alias_response.status_code == 200
    with Session(db_engine) as session:
        bag = session.scalar(select(BagModel).where(BagModel.slug == "chloe-paddington"))
        assert bag is not None
        assert bag.recompute_required
        assert bag.recompute_flagged_at is not None
        reset_flags(session)

    with TestClient(app) as client:
        patch_response = client.patch(
            "/admin/catalog/bags/chloe-paddington",
            headers=auth_headers(),
            json={"editorial_summary": "Updated public summary."},
        )

    assert patch_response.status_code == 200
    with Session(db_engine) as session:
        bag = session.scalar(select(BagModel).where(BagModel.slug == "chloe-paddington"))
        assert bag is not None
        assert not bag.recompute_required


def test_global_exclusion_flags_all_bags(db_engine: Engine) -> None:
    suffix = uuid4().hex
    with Session(db_engine) as session:
        seed(session)
        reset_flags(session)

    with TestClient(app) as client:
        response = client.post(
            "/admin/catalog/exclusions",
            headers=auth_headers(),
            json={"term": f"phase four global test {suffix}", "reason": RejectionReason.wrong_model.value},
        )

    assert response.status_code == 200
    with Session(db_engine) as session:
        flags = session.scalars(select(BagModel.recompute_required)).all()
        assert flags
        assert all(flags)


def test_referenced_variant_delete_conflicts(db_engine: Engine) -> None:
    suffix = uuid4().hex
    with Session(db_engine) as session:
        seed(session)
        bag = session.scalar(select(BagModel).where(BagModel.slug == "chloe-paddington"))
        assert bag is not None
        variant = BagVariant(
            bag_model_id=bag.id,
            name=f"Referenced Variant Test {suffix}",
            kind=VariantKind.edition,
            is_separate_market=True,
        )
        session.add(variant)
        session.flush()
        session.add(
            DailyAggregate(
                bag_model_id=bag.id,
                variant_id=variant.id,
                condition_band=ConditionBand.good,
                observation_date=date(2026, 7, 3),
                active_listing_count=1,
                matched_listing_count=1,
                source_count=1,
            )
        )
        session.commit()
        variant_id = variant.id

    with TestClient(app) as client:
        response = client.delete(
            f"/admin/catalog/bags/chloe-paddington/variants/{variant_id}",
            headers=auth_headers(),
        )

    assert response.status_code == 409


def test_recompute_job_helper_clears_flags(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        seed(session)
        bag = session.scalar(select(BagModel).where(BagModel.slug == "chloe-paddington"))
        assert bag is not None
        bag.recompute_required = True
        bag.recompute_flagged_at = None
        session.commit()
        bag_id = bag.id

    with Session(db_engine) as session:
        clear_recompute_flags(session, {bag_id})
        session.commit()

    with Session(db_engine) as session:
        bag = session.get(BagModel, bag_id)
        assert bag is not None
        assert not bag.recompute_required
        assert bag.recompute_flagged_at is None
