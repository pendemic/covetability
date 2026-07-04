from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.conditions.normalize import band_distance, normalize_condition
from app.contract import CONDITION_ACCURACY_TARGET, GoldLabelVerdict
from app.models import BagModel, GoldLabel, ListingRaw


@dataclass(frozen=True)
class ConditionEvaluationReport:
    total_labels: int
    evaluated_labels: int
    abstentions: int
    exact: int
    adjacent: int
    wrong: int
    per_bag: dict[str, dict[str, int]]
    rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        denominator = self.exact + self.adjacent + self.wrong
        return 1.0 if denominator == 0 else (self.exact + (0.5 * self.adjacent)) / denominator

    @property
    def coverage(self) -> float:
        return 1.0 if self.evaluated_labels == 0 else (self.evaluated_labels - self.abstentions) / self.evaluated_labels

    @property
    def passes_targets(self) -> bool:
        return self.accuracy >= CONDITION_ACCURACY_TARGET


def evaluate_conditions(
    session: Session,
    *,
    bag_slug: str | None = None,
    export_path: Path | None = None,
) -> ConditionEvaluationReport:
    bag_slug_by_id = {bag.id: bag.slug for bag in session.scalars(select(BagModel)).all()}
    labels_query = select(GoldLabel).where(
        GoldLabel.verdict == GoldLabelVerdict.accept,
        GoldLabel.condition_band.is_not(None),
    )
    if bag_slug is not None:
        bag_id = next((bag_id for bag_id, slug in bag_slug_by_id.items() if slug == bag_slug), None)
        if bag_id is None:
            raise ValueError(f"Unknown bag slug: {bag_slug}")
        labels_query = labels_query.where(GoldLabel.bag_model_id == bag_id)

    labels = session.scalars(labels_query.order_by(GoldLabel.id)).all()
    listings_by_item = {
        listing.marketplace_item_id: listing
        for listing in session.scalars(select(ListingRaw).order_by(ListingRaw.id)).all()
    }
    counts = {"exact": 0, "adjacent": 0, "wrong": 0, "abstentions": 0}
    per_bag: dict[str, dict[str, int]] = {}
    rows: list[dict[str, Any]] = []

    for label in labels:
        bag_slug_value = bag_slug_by_id[label.bag_model_id]
        per_bag.setdefault(bag_slug_value, {"exact": 0, "adjacent": 0, "wrong": 0, "abstentions": 0})
        listing = listings_by_item.get(label.marketplace_item_id)
        if listing is None:
            continue

        assessment = normalize_condition(
            listing.condition_raw,
            listing.title,
            bag_slug=bag_slug_value,
        )
        outcome = classify_condition(label.condition_band, assessment.band)
        counts[outcome] += 1
        per_bag[bag_slug_value][outcome] += 1
        rows.append(
            {
                "item_id": label.marketplace_item_id,
                "bag_slug": bag_slug_value,
                "title": listing.title,
                "condition_raw": listing.condition_raw or "",
                "expected": label.condition_band.value,
                "predicted": assessment.band.value if assessment.band else "",
                "confidence": assessment.confidence.value,
                "signals": [signal.term for signal in assessment.signals],
                "outcome": outcome,
            }
        )

    report = ConditionEvaluationReport(
        total_labels=len(labels),
        evaluated_labels=len(rows),
        abstentions=counts["abstentions"],
        exact=counts["exact"],
        adjacent=counts["adjacent"],
        wrong=counts["wrong"],
        per_bag=per_bag,
        rows=rows,
    )
    if export_path is not None:
        write_export(export_path, rows)
    return report


def classify_condition(expected, predicted) -> str:
    if predicted is None:
        return "abstentions"
    distance = band_distance(expected, predicted)
    if distance == 0:
        return "exact"
    if distance == 1:
        return "adjacent"
    return "wrong"


def write_export(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        if not rows:
            return
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
