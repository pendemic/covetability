"""Weekly trends ingestion orchestration (Phase 5).

Pulls/imports per-bag trend windows, appends ``trend_pulls`` audit rows
(including reproducibility trials for the stability gate), stitches the
canonical and alias windows, classifies each week, and refreshes
``search_signal_weekly`` (delete-then-insert, since it is fully derived).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.contract import TrendQueryRole
from app.models import BagModel, SearchSignalWeekly, TrendPull
from app.trends.classify import classify_series
from app.trends.source import TrendRequest, TrendSource, TrendWindow, WeeklyPoint
from app.trends.stitch import stitch_windows


@dataclass
class TrendsSummary:
    bag_stats: dict[str, dict[str, Any]] = field(default_factory=dict)


def run_weekly_trends(
    session: Session,
    source: TrendSource,
    *,
    anchor_term: str,
    now: datetime | None = None,
) -> TrendsSummary:
    now = now or datetime.now(UTC)
    bags = session.scalars(
        select(BagModel).options(selectinload(BagModel.aliases)).order_by(BagModel.slug)
    ).all()
    summary = TrendsSummary()

    for bag in bags:
        canonical_query = bag.model_name
        alias_query = _top_alias(bag)
        request = TrendRequest(
            bag_slug=bag.slug,
            canonical_query=canonical_query,
            alias_query=alias_query,
            anchor_term=anchor_term,
        )
        windows = list(source.fetch(request))

        pulls_written = _write_pulls(session, bag.id, source.source_name, windows, now)

        canonical_windows = [w for w in windows if w.role == TrendQueryRole.canonical]
        alias_windows = [w for w in windows if w.role == TrendQueryRole.alias]
        canonical_series = stitch_windows(canonical_windows).points if canonical_windows else []
        alias_series = stitch_windows(alias_windows).points if alias_windows else []
        low_volume_flag = any(w.low_volume for w in canonical_windows)

        signals = classify_series(canonical_series, alias_series or None, low_volume_flag=low_volume_flag)
        _write_signals(session, bag.id, signals)

        latest = signals[-1] if signals else None
        summary.bag_stats[bag.slug] = {
            "pulls_written": pulls_written,
            "weeks": len(signals),
            "latest_bucket": latest.bucket.value if latest else None,
            "latest_alias_agrees": (latest.alias_agrees if latest else None),
            "latest_low_volume": (latest.low_volume if latest else None),
        }

    session.flush()
    return summary


def _top_alias(bag: BagModel) -> str | None:
    aliases = sorted(bag.aliases, key=lambda a: a.id)
    for alias in aliases:
        if alias.type.value in {"alias", "marketplace_term"}:
            return alias.alias
    return aliases[0].alias if aliases else None


def _serialize(points: list[WeeklyPoint]) -> list[dict[str, Any]]:
    return [{"week": p.week.isoformat(), "value": round(p.value, 4)} for p in points]


def _write_pulls(
    session: Session,
    bag_id: int,
    source_name: str,
    windows: list[TrendWindow],
    now: datetime,
) -> int:
    written = 0
    for window in windows:
        # Reproducibility trials first, then the base pull, so the base is the
        # most-recent same-window row if a consumer ever prefers the latest.
        for trial in window.reproducibility_trials:
            session.add(
                TrendPull(
                    bag_model_id=bag_id,
                    query_role=window.role,
                    query_text=window.query_text,
                    source=source_name,
                    anchor_term=window.anchor_term,
                    window_start=window.window_start,
                    window_end=window.window_end,
                    pulled_at=now,
                    low_volume=window.low_volume,
                    weekly_points=_serialize(trial),
                )
            )
            written += 1
        session.add(
            TrendPull(
                bag_model_id=bag_id,
                query_role=window.role,
                query_text=window.query_text,
                source=source_name,
                anchor_term=window.anchor_term,
                window_start=window.window_start,
                window_end=window.window_end,
                pulled_at=now,
                low_volume=window.low_volume,
                weekly_points=_serialize(window.points),
            )
        )
        written += 1
    return written


def _write_signals(session: Session, bag_id: int, signals: list) -> None:
    session.execute(delete(SearchSignalWeekly).where(SearchSignalWeekly.bag_model_id == bag_id))
    for signal in signals:
        session.add(
            SearchSignalWeekly(
                bag_model_id=bag_id,
                week_start=signal.week_start,
                stitched_value=round(signal.stitched_value, 3),
                slope_8w=round(signal.slope_8w, 4),
                slope_4w=round(signal.slope_4w, 4),
                bucket=signal.bucket,
                alias_agrees=signal.alias_agrees,
                low_volume=signal.low_volume,
                series_length=signal.series_length,
                input_trace=signal.trace,
            )
        )
