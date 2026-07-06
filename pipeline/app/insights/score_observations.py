from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.insights.observations import Observation
from app.models import BagModel
from app.scoring.decomposition import decompose_score_day

COMPONENT_LABELS = {
    "search_momentum": "Search interest",
    "active_inventory_momentum": "Active inventory",
    "asking_price_momentum": "Asking prices",
    "marketplace_breadth": "Marketplace breadth",
    "listing_turnover_proxy": "Listing turnover proxy",
}


def generate_score_observations(session: Session, bag: BagModel, as_of: date | None) -> list[dict]:
    if as_of is None:
        return []
    decomposition = decompose_score_day(session, bag.id, as_of)
    if decomposition is None:
        return []
    ranked = sorted(decomposition.components, key=lambda item: abs(item.delta), reverse=True)
    observations: list[Observation] = []
    for item in ranked:
        if len(observations) >= 5:
            break
        if abs(item.delta) < 0.1:
            continue
        label = COMPONENT_LABELS.get(item.component, item.component.replace("_", " "))
        sentence = _sentence(item.component, label, item.delta, item.trace)
        observations.append(
            Observation(
                metric=item.component,
                window_days=1,
                band=None,
                from_value=str(item.contribution_previous),
                to_value=str(item.contribution_now),
                percent_change=None,
                magnitude=Decimal(str(round(abs(item.delta), 2))),
                sentence=sentence,
            )
        )
    return [item.as_dict() for item in observations]


def _sentence(component: str, label: str, delta: float, trace: dict) -> str:
    direction = "added" if delta > 0 else "reduced"
    amount = abs(delta)
    if component == "asking_price_momentum":
        divergence = trace.get("divergence", {})
        if divergence.get("consecutive_flat_neg_weeks", 0):
            return f"Asking prices rose without matching interest, {direction} {amount:.1f} points."
    if component == "search_momentum":
        bucket = trace.get("bucket")
        return f"{label} moved to {bucket or 'the latest bucket'}, {direction} {amount:.1f} points."
    return f"{label} {direction} {amount:.1f} points in the latest score move."
