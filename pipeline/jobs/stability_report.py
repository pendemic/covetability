from __future__ import annotations

from app.db import SessionLocal
from app.scoring.stability import run_stability


def _mark(passed: bool) -> str:
    return "pass" if passed else "FAIL"


def main() -> int:
    with SessionLocal() as session:
        decision = run_stability(session)

    print("Search-signal stability gate (score-spec §6)")
    print("bag,weeks,flip_rate,flip,repro_trials,repro_share,repro,alias_share,alias,window_share,window")
    for r in decision.per_bag:
        print(
            f"{r.slug},{r.weeks},{r.flip_rate},{_mark(r.flip_pass)},"
            f"{r.reproducibility_trials},{r.reproducibility_share},{_mark(r.reproducibility_pass)},"
            f"{r.alias_share},{_mark(r.alias_pass)},{r.window_share},{_mark(r.window_pass)}"
        )
    print()
    print(f"DECISION: search weight = {decision.recommended_search_weight}%")
    print(f"rationale: {decision.rationale}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
