"""Shared state for operator-triggered pipeline refreshes.

The admin API spawns ``jobs.refresh`` as a detached subprocess; that process and
the API both read/write a small JSON status file so the admin UI can poll
progress. Kept intentionally file-based (no new table/migration) since it is a
single-operator control surface.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
STATUS_PATH = PIPELINE_ROOT / ".runtime" / "refresh_status.json"
STALE_AFTER_SECONDS = 45 * 60

# (key, human label) in execution order.
STEP_LABELS: list[tuple[str, str]] = [
    ("snapshot", "Snapshot"),
    ("match", "Match"),
    ("normalize", "Normalize conditions"),
    ("aggregate", "Aggregate"),
    ("score", "Score"),
]


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def read_status() -> dict[str, Any] | None:
    try:
        with STATUS_PATH.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def write_status(status: dict[str, Any]) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(STATUS_PATH.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(status, handle)
        os.replace(tmp, STATUS_PATH)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def new_run(run_id: str, source: str) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "source": source,
        "status": "running",
        "started_at": now_iso(),
        "finished_at": None,
        "steps": [
            {"key": key, "label": label, "status": "pending", "summary": None, "finished_at": None}
            for key, label in STEP_LABELS
        ],
    }


def is_running(status: dict[str, Any] | None) -> bool:
    """True only if a run is marked running and not older than the stale window."""
    if not status or status.get("status") != "running":
        return False
    started = status.get("started_at")
    if not started:
        return False
    try:
        started_dt = datetime.fromisoformat(started)
    except ValueError:
        return False
    return (datetime.now(UTC) - started_dt).total_seconds() < STALE_AFTER_SECONDS
