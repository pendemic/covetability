"""Fixture-replay trends source (Phase 5).

Reads ``fixtures/trends/<slug>.json`` and expands the compact form into
anchor-rescaled weekly windows. Reproducibility trials are generated with a
deterministic per-bag seed so the stability harness has repeatable jitter.
"""

from __future__ import annotations

import json
import random
from collections.abc import Iterable
from datetime import date, timedelta
from pathlib import Path

from app.contract import TrendQueryRole
from app.trends.source import TrendRequest, TrendWindow, WeeklyPoint


class FixtureTrendSource:
    source_name = "fixtures"

    def __init__(self, fixtures_dir: Path) -> None:
        self.fixtures_dir = fixtures_dir

    def fetch(self, request: TrendRequest) -> Iterable[TrendWindow]:
        path = self.fixtures_dir / f"{request.bag_slug}.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        anchor = data.get("anchor_term", request.anchor_term)
        week_start = date.fromisoformat(data["week_start"])
        windows: list[TrendWindow] = []

        canonical_values = [float(v) for v in data.get("canonical", [])]
        canonical_points = _weekly_points(week_start, canonical_values)
        repro = data.get("reproducibility", {})
        trials = _reproducibility_trials(
            request.bag_slug,
            canonical_points,
            count=int(repro.get("trials", 0)),
            jitter=float(repro.get("jitter", 0.0)),
        )
        windows.append(
            TrendWindow(
                role=TrendQueryRole.canonical,
                query_text=data.get("canonical_query", request.canonical_query),
                anchor_term=anchor,
                window_start=week_start,
                window_end=_week_end(week_start, canonical_points),
                points=canonical_points,
                low_volume=bool(data.get("low_volume", False)),
                reproducibility_trials=trials,
            )
        )

        alias_values = [float(v) for v in data.get("alias", [])]
        if alias_values:
            alias_points = _weekly_points(week_start, alias_values)
            windows.append(
                TrendWindow(
                    role=TrendQueryRole.alias,
                    query_text=data.get("alias_query") or (request.alias_query or ""),
                    anchor_term=anchor,
                    window_start=week_start,
                    window_end=_week_end(week_start, alias_points),
                    points=alias_points,
                    low_volume=bool(data.get("low_volume", False)),
                )
            )

        second = data.get("second_window")
        if second:
            if "week_offset" in second:
                second_start = week_start + timedelta(days=7 * int(second["week_offset"]))
            else:
                second_start = date.fromisoformat(second["week_start"])
            second_points = _weekly_points(second_start, [float(v) for v in second["values"]])
            windows.append(
                TrendWindow(
                    role=TrendQueryRole.canonical,
                    query_text=data.get("canonical_query", request.canonical_query),
                    anchor_term=anchor,
                    window_start=second_start,
                    window_end=_week_end(second_start, second_points),
                    points=second_points,
                    low_volume=bool(data.get("low_volume", False)),
                )
            )

        return windows


def _weekly_points(week_start: date, values: list[float]) -> list[WeeklyPoint]:
    return [WeeklyPoint(week=week_start + timedelta(days=7 * i), value=v) for i, v in enumerate(values)]


def _week_end(week_start: date, points: list[WeeklyPoint]) -> date:
    if not points:
        return week_start
    return points[-1].week


def _reproducibility_trials(
    slug: str,
    base: list[WeeklyPoint],
    *,
    count: int,
    jitter: float,
) -> list[list[WeeklyPoint]]:
    if count <= 0 or not base:
        return []
    rng = random.Random(f"trends:{slug}")
    trials: list[list[WeeklyPoint]] = []
    for _ in range(count):
        trials.append(
            [
                WeeklyPoint(week=p.week, value=max(0.0, p.value + rng.uniform(-jitter, jitter)))
                for p in base
            ]
        )
    return trials
