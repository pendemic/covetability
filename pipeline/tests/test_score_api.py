from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.main import app
from app.scoring.compute import compute_bag_day
from app.settings import get_settings
from tests.test_score_compute import DAY1, DAY2, build_scoreable_bag, cleanup


def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().admin_secret}"}


def test_score_api_requires_auth(db_engine: Engine) -> None:
    with TestClient(app) as client:
        assert client.get("/admin/score/bags").status_code == 401


def test_score_timeline_and_decomposition(db_engine: Engine) -> None:
    with Session(db_engine) as session:
        bag = build_scoreable_bag(session)
        compute_bag_day(session, bag, DAY1)
        compute_bag_day(session, bag, DAY2)
        session.commit()
        slug = bag.slug

    try:
        with TestClient(app) as client:
            bags = client.get("/admin/score/bags", headers=auth_headers())
            assert bags.status_code == 200
            assert bags.json()["published"] is False

            timeline = client.get(f"/admin/score/{slug}/timeline", headers=auth_headers())
            assert timeline.status_code == 200
            rows = timeline.json()["timeline"]
            assert len(rows) == 2
            assert rows[-1]["scored"] is True

            decomp = client.get(
                f"/admin/score/{slug}/decomposition",
                headers=auth_headers(),
                params={"date": DAY2.isoformat()},
            )
            assert decomp.status_code == 200
            body = decomp.json()
            # The audit invariant: per-component deltas sum to the actual raw delta.
            assert abs(body["decomposition_sum"] - body["raw_delta"]) < 0.02

            gates = client.get(f"/admin/score/{slug}/gates", headers=auth_headers())
            assert gates.status_code == 200
            assert len(gates.json()["gate_history"]) == 2
    finally:
        with Session(db_engine) as session:
            bag = session.get(type(bag), bag.id)
            cleanup(session, bag)
