from __future__ import annotations

import argparse
from pathlib import Path

from app.conditions.evaluate import evaluate_conditions
from app.contract import CONDITION_ACCURACY_TARGET
from app.db import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate condition normalization against gold labels.")
    parser.add_argument("--bag", help="Limit to one bag slug.")
    parser.add_argument("--export", help="Write a confusion CSV.")
    parser.add_argument("--enforce", action="store_true", help="Exit non-zero below target.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with SessionLocal() as session:
        report = evaluate_conditions(
            session,
            bag_slug=args.bag,
            export_path=Path(args.export) if args.export else None,
        )

    print(f"labels,total={report.total_labels},evaluated={report.evaluated_labels}")
    print(f"accuracy,{report.accuracy:.4f},target,{CONDITION_ACCURACY_TARGET:.4f}")
    print(f"coverage,{report.coverage:.4f},abstentions,{report.abstentions}")
    print(f"confusion,exact={report.exact},adjacent={report.adjacent},wrong={report.wrong}")
    print("bag,exact,adjacent,wrong,abstentions")
    for slug, counts in sorted(report.per_bag.items()):
        print(
            f"{slug},{counts['exact']},{counts['adjacent']},"
            f"{counts['wrong']},{counts['abstentions']}"
        )
    if args.enforce and not report.passes_targets:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
