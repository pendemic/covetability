"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  getRefreshStatus,
  startRefresh,
  type RefreshStatus,
} from "@/lib/adminApi";
import { adminCopy } from "@/lib/adminVocabulary";

const STATUS_LABEL: Record<string, string> = {
  idle: "Idle",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
  pending: "Pending",
};

export default function RefreshPage() {
  const [status, setStatus] = useState<RefreshStatus | null>(null);
  const [source, setSource] = useState<"fixtures" | "live">("fixtures");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(() => {
    getRefreshStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  useEffect(() => {
    load();
    timer.current = setInterval(load, 2000);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [load]);

  const running = status?.status === "running";

  async function onRun() {
    if (source === "live" && !window.confirm("Run a LIVE eBay production pull? This makes real API calls.")) {
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      const result = await startRefresh(source);
      if (result.conflict) {
        setNotice("A refresh is already running.");
      } else if (!result.started) {
        setNotice("Could not start the refresh.");
      }
      load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="adminStack">
      <header className="adminHeader">
        <h1>{adminCopy.dataRefresh}</h1>
        <span className={running ? "adminChip adminChipActive" : "adminChip"}>
          {STATUS_LABEL[status?.status ?? "idle"] ?? status?.status}
        </span>
      </header>

      <section className="adminTool adminStack">
        <p className="adminMuted">
          Runs snapshot → match → normalize → aggregate → score in one detached run.
          Fixtures is safe to run anytime; Live makes real eBay production API calls.
        </p>
        <div className="adminActions">
          <label className="adminField">
            <span>{adminCopy.source}</span>
            <select
              value={source}
              onChange={(event) => setSource(event.target.value as "fixtures" | "live")}
              disabled={running || busy}
            >
              <option value="fixtures">Fixtures</option>
              <option value="live">Live (production)</option>
            </select>
          </label>
          <button className="adminButton" type="button" onClick={onRun} disabled={running || busy}>
            {running ? "Running…" : adminCopy.runRefresh}
          </button>
        </div>
        {notice ? <p className="adminMuted">{notice}</p> : null}
        {status?.source ? (
          <p className="adminMuted">
            Last run source: <strong>{status.source}</strong>
            {status.started_at ? ` · started ${new Date(status.started_at).toLocaleString()}` : ""}
            {status.finished_at ? ` · finished ${new Date(status.finished_at).toLocaleString()}` : ""}
          </p>
        ) : null}
      </section>

      {status && status.steps.length ? (
        <section className="adminTool adminStack">
          <h2>Steps</h2>
          <table className="adminTable">
            <thead>
              <tr>
                <th>Step</th>
                <th>Status</th>
                <th>Summary</th>
              </tr>
            </thead>
            <tbody>
              {status.steps.map((step) => (
                <tr key={step.key} className={step.status === "pending" ? "adminMuted" : undefined}>
                  <td>{step.label}</td>
                  <td>{STATUS_LABEL[step.status] ?? step.status}</td>
                  <td className="adminMono">{step.summary ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : (
        <p className="adminMuted">{adminCopy.noRows}</p>
      )}
    </div>
  );
}
