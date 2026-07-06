"""pytrends live trends source (Phase 5, optional dependency).

pytrends is unofficial and can break or rate-limit without notice, so it is an
optional dependency imported lazily and isolated behind the ``TrendSource``
interface. CSV and fixture sources are the fallbacks. Only derived weekly points
(anchor-rescaled against a fixed anchor term) are returned; raw Google data is
never persisted, consistent with not redistributing it.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.contract import SEARCH_LOW_VOLUME_FLOOR, TrendQueryRole
from app.trends.source import TrendRequest, TrendWindow, WeeklyPoint


class PytrendsTrendSource:
    source_name = "pytrends"

    def __init__(self, *, anchor_term: str, timeframe: str = "today 12-m", geo: str = "US") -> None:
        self.anchor_term = anchor_term
        self.timeframe = timeframe
        self.geo = geo

    def fetch(self, request: TrendRequest) -> Iterable[TrendWindow]:
        try:
            from pytrends.request import TrendReq
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "TRENDS_SOURCE=pytrends requires the optional 'trends' dependency group "
                "(uv sync --group trends)."
            ) from exc

        pytrends = TrendReq(hl="en-US", tz=0)
        windows: list[TrendWindow] = []
        queries = [(TrendQueryRole.canonical, request.canonical_query)]
        if request.alias_query:
            queries.append((TrendQueryRole.alias, request.alias_query))

        for role, query_text in queries:
            window = self._pull(pytrends, role, query_text)
            if window is not None:
                windows.append(window)
        return windows

    def _pull(self, pytrends, role: TrendQueryRole, query_text: str) -> TrendWindow | None:  # pragma: no cover
        # Anchor rescale: pull the query alongside the fixed anchor so values are
        # comparable across windows, then divide out the anchor level.
        pytrends.build_payload([query_text, self.anchor_term], timeframe=self.timeframe, geo=self.geo)
        frame = pytrends.interest_over_time()
        if frame is None or frame.empty or query_text not in frame:
            return None
        points: list[WeeklyPoint] = []
        for stamp, row in frame.iterrows():
            anchor_value = float(row.get(self.anchor_term, 0.0)) or 1.0
            rescaled = float(row[query_text]) / anchor_value * 100.0
            points.append(WeeklyPoint(week=stamp.date(), value=rescaled))
        if not points:
            return None
        low_volume = all(p.value < SEARCH_LOW_VOLUME_FLOOR for p in points)
        return TrendWindow(
            role=role,
            query_text=query_text,
            anchor_term=self.anchor_term,
            window_start=points[0].week,
            window_end=points[-1].week,
            points=points,
            low_volume=low_volume,
        )
