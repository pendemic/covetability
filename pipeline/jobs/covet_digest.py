from __future__ import annotations

import json
from collections import defaultdict

from sqlalchemy import select

from app.db import SessionLocal
from app.models import BagModel, CovetListWatch, ScoreDaily


def build_digest_payloads() -> list[dict]:
    with SessionLocal() as session:
        watches = session.execute(
            select(CovetListWatch, BagModel)
            .join(BagModel, BagModel.id == CovetListWatch.bag_model_id)
            .order_by(CovetListWatch.email, BagModel.slug)
        ).all()
        by_email: dict[str, list[dict]] = defaultdict(list)
        for watch, bag in watches:
            score = session.scalars(
                select(ScoreDaily)
                .where(ScoreDaily.bag_model_id == bag.id, ScoreDaily.published.is_(True))
                .order_by(ScoreDaily.observation_date.desc())
                .limit(1)
            ).first()
            by_email[watch.email].append(
                {
                    "slug": bag.slug,
                    "model_name": bag.model_name,
                    "score": float(score.publication_value) if score and score.publication_value is not None else None,
                    "classification": score.classification.value if score and score.classification else None,
                    "direction": score.direction.value if score and score.direction else None,
                }
            )
    return [{"email": email, "bags": bags, "send": False} for email, bags in sorted(by_email.items())]


def main() -> int:
    print(json.dumps(build_digest_payloads(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
