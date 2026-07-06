from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.models import ScoreConfig
from app.scoring.stability import run_stability


def main() -> int:
    with SessionLocal() as session:
        decision = run_stability(session)
        stmt = (
            insert(ScoreConfig)
            .values(
                id=1,
                search_weight=decision.recommended_search_weight,
                decided_at=datetime.now(UTC),
                rationale=decision.rationale,
            )
            .on_conflict_do_update(
                index_elements=[ScoreConfig.id],
                set_={
                    "search_weight": decision.recommended_search_weight,
                    "decided_at": datetime.now(UTC),
                    "rationale": decision.rationale,
                },
            )
        )
        session.execute(stmt)
        session.commit()

    print(f"search weight={decision.recommended_search_weight}")
    print(f"rationale: {decision.rationale}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
