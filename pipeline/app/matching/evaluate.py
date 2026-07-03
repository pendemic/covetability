from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contract import (
    MATCH_PRECISION_TARGET,
    MATCH_RECALL_TARGET,
    VARIANT_ATTRIBUTION_TARGET,
    GoldLabelOrigin,
    GoldLabelVerdict,
    MatchStatus,
)
from app.matching.matcher import CatalogIndex, MatchResult, match_listing
from app.models import BagModel, BagVariant, GoldLabel, ListingRaw


@dataclass(frozen=True)
class EvaluationReport:
    total_labels: int
    evaluated_labels: int
    unevaluable_labels: int
    true_positive: int
    false_positive: int
    false_negative: int
    review_recoverable: int
    variant_correct: int
    variant_total: int
    false_positive_reasons: dict[str, int]
    per_bag: dict[str, dict[str, int]]
    rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def precision(self) -> float:
        denominator = self.true_positive + self.false_positive
        return 1.0 if denominator == 0 else self.true_positive / denominator

    @property
    def recall(self) -> float:
        denominator = self.true_positive + self.false_negative
        return 1.0 if denominator == 0 else self.true_positive / denominator

    @property
    def variant_attribution(self) -> float:
        return 1.0 if self.variant_total == 0 else self.variant_correct / self.variant_total

    @property
    def passes_targets(self) -> bool:
        return (
            self.precision >= MATCH_PRECISION_TARGET
            and self.recall >= MATCH_RECALL_TARGET
            and self.variant_attribution >= VARIANT_ATTRIBUTION_TARGET
        )


def evaluate_matcher(
    session: Session,
    *,
    bag_slug: str | None = None,
    gold_origin: str = "all",
    export_path: Path | None = None,
) -> EvaluationReport:
    index = CatalogIndex.from_session(session)
    bag_slug_by_id = {bag.id: bag.slug for bag in session.scalars(select(BagModel)).all()}
    variant_name_by_id = {variant.id: variant.name for variant in session.scalars(select(BagVariant)).all()}
    bag_id_filter = None
    if bag_slug is not None:
        bag_id_filter = next((bag_id for bag_id, slug in bag_slug_by_id.items() if slug == bag_slug), None)
        if bag_id_filter is None:
            raise ValueError(f"Unknown bag slug: {bag_slug}")

    query = select(GoldLabel).order_by(GoldLabel.id)
    if bag_id_filter is not None:
        query = query.where(GoldLabel.bag_model_id == bag_id_filter)
    if gold_origin == "human":
        query = query.where(GoldLabel.origin.in_([GoldLabelOrigin.labeling_ui, GoldLabelOrigin.review_queue]))
    elif gold_origin != "all":
        query = query.where(GoldLabel.origin == GoldLabelOrigin(gold_origin))

    labels = session.scalars(query).all()
    counters = {
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "review": 0,
        "variant_correct": 0,
        "variant_total": 0,
        "unevaluable": 0,
    }
    false_positive_reasons: dict[str, int] = {}
    per_bag: dict[str, dict[str, int]] = {}
    rows: list[dict[str, Any]] = []

    listings_by_item = {
        listing.marketplace_item_id: listing
        for listing in session.scalars(select(ListingRaw).order_by(ListingRaw.id)).all()
    }

    for label in labels:
        expected_bag = bag_slug_by_id[label.bag_model_id]
        per_bag.setdefault(expected_bag, {"tp": 0, "fp": 0, "fn": 0, "review": 0, "total": 0})
        per_bag[expected_bag]["total"] += 1

        listing = listings_by_item.get(label.marketplace_item_id)
        if listing is None:
            counters["unevaluable"] += 1
            rows.append(export_row(label, expected_bag, None, None, "unevaluable"))
            continue

        candidate_slug = bag_slug_by_id.get(listing.candidate_bag_model_id, expected_bag)
        result = match_listing(listing.title, index, candidate_bag_slug=candidate_slug)
        expected_variant = variant_name_by_id.get(label.accepted_variant_id)
        outcome = classify(label, expected_bag, expected_variant, result)
        apply_outcome(outcome, counters, per_bag[expected_bag])
        if outcome == "fp" and label.rejection_reason is not None:
            reason = label.rejection_reason.value
            false_positive_reasons[reason] = false_positive_reasons.get(reason, 0) + 1
        rows.append(export_row(label, expected_bag, expected_variant, result, outcome, listing.title))

    report = EvaluationReport(
        total_labels=len(labels),
        evaluated_labels=len(labels) - counters["unevaluable"],
        unevaluable_labels=counters["unevaluable"],
        true_positive=counters["tp"],
        false_positive=counters["fp"],
        false_negative=counters["fn"],
        review_recoverable=counters["review"],
        variant_correct=counters["variant_correct"],
        variant_total=counters["variant_total"],
        false_positive_reasons=false_positive_reasons,
        per_bag=per_bag,
        rows=rows,
    )
    if export_path is not None:
        write_export(export_path, rows)
    return report


def classify(
    label: GoldLabel,
    expected_bag: str,
    expected_variant: str | None,
    result: MatchResult,
) -> str:
    if label.verdict == GoldLabelVerdict.reject:
        if result.status == MatchStatus.auto_accepted and result.bag_slug == expected_bag:
            return "fp"
        return "tn"

    if result.status == MatchStatus.auto_accepted and result.bag_slug == expected_bag:
        if expected_variant is not None:
            return "tp_variant_correct" if result.variant_name == expected_variant else "tp_variant_missed"
        return "tp"
    if result.status == MatchStatus.needs_review and result.bag_slug == expected_bag:
        return "review"
    return "fn"


def apply_outcome(outcome: str, counters: dict[str, int], bag_counts: dict[str, int]) -> None:
    if outcome.startswith("tp"):
        counters["tp"] += 1
        bag_counts["tp"] += 1
        if outcome in {"tp_variant_correct", "tp_variant_missed"}:
            counters["variant_total"] += 1
            if outcome == "tp_variant_correct":
                counters["variant_correct"] += 1
        return
    if outcome == "fp":
        counters["fp"] += 1
        bag_counts["fp"] += 1
        return
    if outcome == "fn":
        counters["fn"] += 1
        bag_counts["fn"] += 1
        return
    if outcome == "review":
        counters["fn"] += 1
        counters["review"] += 1
        bag_counts["fn"] += 1
        bag_counts["review"] += 1


def export_row(
    label: GoldLabel,
    expected_bag: str,
    expected_variant: str | None,
    result: MatchResult | None,
    outcome: str,
    title: str | None = None,
) -> dict[str, Any]:
    selected = {}
    if result is not None:
        selected = result.trace.get("candidates", [{}])[0] if result.trace.get("candidates") else {}
    return {
        "item_id": label.marketplace_item_id,
        "title": title or "",
        "expected_bag": expected_bag,
        "expected_verdict": label.verdict.value,
        "expected_reason": label.rejection_reason.value if label.rejection_reason else "",
        "expected_variant": expected_variant or "",
        "predicted_status": result.status.value if result else "",
        "predicted_bag": result.bag_slug if result else "",
        "predicted_variant": result.variant_name if result else "",
        "confidence": result.confidence if result else "",
        "outcome": outcome,
        "top_hits": selected.get("hits", []),
        "exclusions": selected.get("exclusions", []),
    }


def write_export(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
