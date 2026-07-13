"""Orchestrate a full pipeline refresh as a single detached run.

Runs the daily sequence (snapshot -> match -> normalize -> aggregate -> score),
one step per subprocess, writing progress to the shared status file after each so
the admin UI can poll it. Env (EBAY_SOURCE, EBAY_ENVIRONMENT, ...) is inherited
from the parent, so the admin endpoint controls fixtures-vs-live.

    uv run python -m jobs.refresh                 # fixtures (default)
    EBAY_SOURCE=live uv run python -m jobs.refresh
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime

from app.refresh_status import PIPELINE_ROOT, new_run, now_iso, write_status

# Steps and whether they take a --date arg. The snapshot stamps listings with the
# UTC observation date; aggregate/score default to *local* date.today(), which can
# differ from UTC around midnight and silently produce empty output. Pinning one
# UTC date for the whole run keeps every step aligned.
STEPS: list[tuple[str, str, bool]] = [
    ("snapshot", "jobs.daily_snapshot", True),
    ("match", "jobs.run_matching", False),
    ("normalize", "jobs.normalize_conditions", False),
    ("aggregate", "jobs.daily_aggregates", True),
    ("score", "jobs.daily_score", True),
]


def main() -> int:
    source = os.environ.get("EBAY_SOURCE", "fixtures")
    run_id = os.environ.get("REFRESH_RUN_ID") or uuid.uuid4().hex[:12]
    run_date = datetime.now(UTC).date().isoformat()
    status = new_run(run_id, source)
    write_status(status)
    steps_by_key = {step["key"]: step for step in status["steps"]}

    overall_ok = True
    for key, module, takes_date in STEPS:
        step = steps_by_key[key]
        step["status"] = "running"
        write_status(status)

        command = [sys.executable, "-m", module]
        if takes_date:
            command += ["--date", run_date]
        proc = subprocess.run(
            command,
            cwd=str(PIPELINE_ROOT),
            env=os.environ.copy(),
            capture_output=True,
            text=True,
        )
        stdout_lines = (proc.stdout or "").strip().splitlines()
        step["finished_at"] = now_iso()
        if proc.returncode == 0:
            step["status"] = "succeeded"
            step["summary"] = stdout_lines[-1] if stdout_lines else ""
            write_status(status)
        else:
            stderr_lines = (proc.stderr or "").strip().splitlines()
            step["status"] = "failed"
            step["summary"] = (stderr_lines[-1] if stderr_lines else "") or "step failed"
            overall_ok = False
            write_status(status)
            break

    status["status"] = "succeeded" if overall_ok else "failed"
    status["finished_at"] = now_iso()
    write_status(status)
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
