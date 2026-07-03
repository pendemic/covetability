"use client";

import { useEffect, useState } from "react";

import { getIngestionSummary, Summary } from "@/lib/adminApi";
import { adminCopy } from "@/lib/adminVocabulary";

export default function AdminDashboardPage() {
  const [summary, setSummary] = useState<Summary | null>(null);

  useEffect(() => {
    getIngestionSummary().then(setSummary).catch(() => setSummary(null));
  }, []);

  return (
    <div className="adminStack">
      <header className="adminHeader">
        <h1>{adminCopy.dashboard}</h1>
      </header>

      <section className="adminGrid">
        <div className="adminPanel adminPanelWide">
          <h2>{adminCopy.snapshotRuns}</h2>
          <table className="adminTable">
            <thead>
              <tr>
                <th>Date</th>
                <th>Source</th>
                <th>Status</th>
                <th>Rows</th>
                <th>Ended</th>
              </tr>
            </thead>
            <tbody>
              {summary?.snapshot_runs.length ? (
                summary.snapshot_runs.map((run) => (
                  <tr key={run.id}>
                    <td>{run.run_date}</td>
                    <td>{run.source}</td>
                    <td>{run.status}</td>
                    <td>{fixtureRowCount(run.bag_counts)}</td>
                    <td>{run.ended_event_count}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5}>{adminCopy.noRows}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="adminPanel">
          <h2>{adminCopy.matchRun}</h2>
          {summary?.last_match_run ? (
            <dl className="adminStack">
              <div>
                <dt>Mode</dt>
                <dd>{summary.last_match_run.mode}</dd>
              </div>
              <div>
                <dt>Version</dt>
                <dd>{summary.last_match_run.matcher_version}</dd>
              </div>
              <div>
                <dt>Rows</dt>
                <dd>{summary.last_match_run.listings_considered}</dd>
              </div>
            </dl>
          ) : (
            <p className="adminMuted">{adminCopy.noRows}</p>
          )}
        </div>

        <div className="adminPanel adminPanelWide">
          <h2>{adminCopy.statusByBag}</h2>
          <table className="adminTable">
            <thead>
              <tr>
                <th>Bag</th>
                <th>Statuses</th>
              </tr>
            </thead>
            <tbody>
              {summary?.match_status_by_bag.map((row) => (
                <tr key={row.bag_slug}>
                  <td>{row.bag_slug}</td>
                  <td>
                    <ul className="adminChipRow">
                      {Object.entries(row.statuses).map(([status, count]) => (
                        <li className="adminChip" key={status}>
                          {status}: {count}
                        </li>
                      ))}
                    </ul>
                  </td>
                </tr>
              )) ?? (
                <tr>
                  <td colSpan={2}>{adminCopy.noRows}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="adminPanel">
          <h2>{adminCopy.goldProgress}</h2>
          <table className="adminTable">
            <thead>
              <tr>
                <th>Bag</th>
                <th>Labels</th>
              </tr>
            </thead>
            <tbody>
              {summary?.gold_progress.map((row) => (
                <tr key={row.bag_slug}>
                  <td>{row.bag_slug}</td>
                  <td>
                    {row.label_count}/{row.candidate_count}
                  </td>
                </tr>
              )) ?? (
                <tr>
                  <td colSpan={2}>{adminCopy.noRows}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function fixtureRowCount(bagCounts: Summary["snapshot_runs"][number]["bag_counts"]) {
  return Object.values(bagCounts).reduce((total, counts) => total + (counts.unique ?? 0), 0);
}
