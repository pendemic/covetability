"use client";

import { useEffect, useState } from "react";

import { QualitySummary, getQualitySummary } from "@/lib/adminApi";
import { adminCopy, conditionBands } from "@/lib/adminVocabulary";

export default function QualityPage() {
  const [summary, setSummary] = useState<QualitySummary | null>(null);

  useEffect(() => {
    getQualitySummary().then(setSummary).catch(() => setSummary(null));
  }, []);

  return (
    <div className="adminStack">
      <header className="adminHeader">
        <h1>{adminCopy.quality}</h1>
        {summary ? (
          <span className="adminMuted">
            {summary.date_from} to {summary.date_to}
          </span>
        ) : null}
      </header>

      <section className="adminStack">
        {summary?.bags.map((bag) => (
          <article className="adminTool adminStack" key={bag.bag_slug}>
            <div className="adminHeader">
              <h2>{bag.bag_slug}</h2>
              <div className="adminChipRow">
                <span className="adminChip">
                  {adminCopy.unbandedShare}: {formatPct(bag.unbanded_share)}
                </span>
                <span className="adminChip">
                  {adminCopy.variantCoverage}: {formatPct(bag.variant_attribution_share)}
                </span>
                <span className="adminChip">Separate rows: {bag.separate_market_rows}</span>
              </div>
            </div>
            <CoverageGrid coverage={bag.band_coverage} />
            <table className="adminTable">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Active</th>
                  <th>{adminCopy.confidence}</th>
                </tr>
              </thead>
              <tbody>
                {bag.active_trend.map((row) => {
                  const confidence = bag.confidence_trend.find((item) => item.date === row.date);
                  return (
                    <tr key={row.date}>
                      <td>{row.date}</td>
                      <td>{row.count}</td>
                      <td>{confidence?.average == null ? "-" : formatPct(confidence.average)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </article>
        )) ?? <p className="adminMuted">{adminCopy.noRows}</p>}
      </section>

      <section className="adminTool adminStack">
        <h2>{adminCopy.alarms}</h2>
        {summary?.alarms.length ? (
          <ul className="adminTraceList">
            {summary.alarms.map((alarm, index) => (
              <li className="adminRejectChip" key={index}>
                {Object.entries(alarm)
                  .map(([key, value]) => `${key}: ${value}`)
                  .join(" | ")}
              </li>
            ))}
          </ul>
        ) : (
          <p className="adminMuted">{adminCopy.noRows}</p>
        )}
      </section>
    </div>
  );
}

function CoverageGrid({
  coverage,
}: {
  coverage: QualitySummary["bags"][number]["band_coverage"];
}) {
  const dates = Object.keys(coverage).sort();
  return (
    <div className="adminCoverage" aria-label={adminCopy.bandCoverage}>
      <div className="adminCoverageCorner" />
      {dates.map((date) => (
        <div className="adminCoverageDate" key={date}>
          {date.slice(5)}
        </div>
      ))}
      {conditionBands.map((band) => (
        <div className="adminCoverageRow" key={band}>
          <div className="adminCoverageBand">{band}</div>
          {dates.map((date) => {
            const cell = coverage[date][band];
            const className = cell.priced
              ? "adminCoverageCell adminCoveragePriced"
              : cell.matched > 0
                ? "adminCoverageCell adminCoverageThin"
                : "adminCoverageCell adminCoverageEmpty";
            return (
              <div className={className} key={`${date}-${band}`} title={`${date} ${band}`}>
                {cell.matched}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function formatPct(value: number) {
  return `${Math.round(value * 100)}%`;
}
