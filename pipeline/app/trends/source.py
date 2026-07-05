"""Trends source protocol and selection (Phase 5).

Mirrors the ``EBAY_SOURCE`` pattern: the source is chosen by ``TRENDS_SOURCE``
(``fixtures`` | ``pytrends`` | ``csv``). pytrends is the primary live collector,
CSV is the manual Google-Trends-export fallback, and fixtures drive CI. Every
source returns anchor-rescaled weekly windows behind one interface so the rest
of the pipeline never learns which one produced the data.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

from app.contract import TrendQueryRole
from app.settings import Settings


@dataclass(frozen=True)
class WeeklyPoint:
    week: date
    value: float


@dataclass(frozen=True)
class TrendWindow:
    """One anchor-rescaled weekly series for a role over a window."""

    role: TrendQueryRole
    query_text: str
    anchor_term: str | None
    window_start: date
    window_end: date
    points: list[WeeklyPoint]
    low_volume: bool = False
    # Extra same-window canonical pulls used only for the stability reproducibility
    # test; not part of the stitched signal.
    reproducibility_trials: list[list[WeeklyPoint]] = field(default_factory=list)


@dataclass(frozen=True)
class TrendRequest:
    bag_slug: str
    canonical_query: str
    alias_query: str | None
    anchor_term: str


class TrendSource(Protocol):
    source_name: str

    def fetch(self, request: TrendRequest) -> Iterable[TrendWindow]:
        raise NotImplementedError


def get_trend_source(settings: Settings) -> TrendSource:
    source = settings.trends_source.lower()
    if source == "fixtures":
        from app.trends.fixtures import FixtureTrendSource

        return FixtureTrendSource(settings.resolve_pipeline_path(settings.trends_fixtures_dir))

    if source == "csv":
        if not settings.trends_csv_dir:
            raise RuntimeError("TRENDS_CSV_DIR is required when TRENDS_SOURCE=csv.")
        from app.trends.csv_source import CsvTrendSource

        return CsvTrendSource(settings.resolve_pipeline_path(settings.trends_csv_dir))

    if source == "pytrends":
        from app.trends.pytrends_source import PytrendsTrendSource

        return PytrendsTrendSource(anchor_term=settings.trends_anchor_term)

    raise RuntimeError("TRENDS_SOURCE must be 'fixtures', 'csv', or 'pytrends'.")
