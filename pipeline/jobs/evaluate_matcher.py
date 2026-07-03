from __future__ import annotations

import argparse
from pathlib import Path

from app.contract import MATCH_PRECISION_TARGET, MATCH_RECALL_TARGET, VARIANT_ATTRIBUTION_TARGET
from app.db import SessionLocal
from app.matching.evaluate import evaluate_matcher


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate the matcher against gold labels.")
    parser.add_argument("--bag", help="Limit to one bag slug.")
    parser.add_argument("--gold-origin", default="all", choices=["fixture_seed", "human", "all"])
    parser.add_argument("--export", help="Write a confusion-listing CSV.")
    parser.add_argument("--enforce", action="store_true", help="Exit non-zero below contract targets.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with SessionLocal() as session:
        report = evaluate_matcher(
            session,
            bag_slug=args.bag,
            gold_origin=args.gold_origin,
            export_path=Path(args.export) if args.export else None,
        )

    print(f"labels,total={report.total_labels},evaluated={report.evaluated_labels},unevaluable={report.unevaluable_labels}")
    print(f"precision,{report.precision:.4f},target,{MATCH_PRECISION_TARGET:.4f}")
    print(f"recall,{report.recall:.4f},target,{MATCH_RECALL_TARGET:.4f}")
    print(f"variant_attribution,{report.variant_attribution:.4f},target,{VARIANT_ATTRIBUTION_TARGET:.4f}")
    print(
        f"confusion,tp={report.true_positive},fp={report.false_positive},"
        f"fn={report.false_negative},review_recoverable={report.review_recoverable}"
    )
    if report.false_positive_reasons:
        print("false_positive_reason,count")
        for reason, count in sorted(report.false_positive_reasons.items()):
            print(f"{reason},{count}")
    print("bag,total,tp,fp,fn,review")
    for slug, counts in sorted(report.per_bag.items()):
        print(
            f"{slug},{counts['total']},{counts['tp']},{counts['fp']},"
            f"{counts['fn']},{counts['review']}"
        )
    if args.enforce and not report.passes_targets:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
