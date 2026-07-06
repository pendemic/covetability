"""CSV trends source: manual Google Trends UI exports (Phase 5 fallback).

Reads ``multiTimeline.csv`` exports saved as ``<slug>.canonical.csv`` and
``<slug>.alias.csv``. The Google Trends export has two metadata lines, a blank
line, then a ``Week,<query>,<anchor>`` header and weekly rows. Values are the
in-window 0-100 Trends index; the anchor column is retained so overlapping
windows can be rescaled during stitching.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from app.contract import SEARCH_LOW_VOLUME_FLOOR, TrendQueryRole
from app.trends.source import TrendRequest, TrendWindow, WeeklyPoint


class CsvTrendSource:
    source_name = "csv"

    def __init__(self, csv_dir: Path) -> None:
        self.csv_dir = csv_dir

    def fetch(self, request: TrendRequest) -> Iterable[TrendWindow]:
        windows: list[TrendWindow] = []
        canonical = self._read(request.bag_slug, TrendQueryRole.canonical, request.canonical_query, request.anchor_term)
        if canonical is not None:
            windows.append(canonical)
        if request.alias_query:
            alias = self._read(request.bag_slug, TrendQueryRole.alias, request.alias_query, request.anchor_term)
            if alias is not None:
                windows.append(alias)
        return windows

    def _read(
        self,
        slug: str,
        role: TrendQueryRole,
        query_text: str,
        anchor_term: str,
    ) -> TrendWindow | None:
        path = self.csv_dir / f"{slug}.{role.value}.csv"
        if not path.exists():
            return None
        points: list[WeeklyPoint] = []
        with path.open(newline="") as handle:
            rows = list(csv.reader(handle))
        started = False
        for row in rows:
            if not row:
                continue
            if not started:
                if row[0].strip().lower().startswith("week"):
                    started = True
                continue
            week = date.fromisoformat(row[0].strip())
            value = _parse_value(row[1]) if len(row) > 1 else 0.0
            points.append(WeeklyPoint(week=week, value=value))
        if not points:
            return None
        low_volume = all(p.value < SEARCH_LOW_VOLUME_FLOOR for p in points)
        return TrendWindow(
            role=role,
            query_text=query_text,
            anchor_term=anchor_term,
            window_start=points[0].week,
            window_end=points[-1].week,
            points=points,
            low_volume=low_volume,
        )


def _parse_value(raw: str) -> float:
    text = raw.strip()
    if text in {"", "<1"}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0
