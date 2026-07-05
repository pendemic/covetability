"use client";

import { useCallback, useEffect, useState } from "react";

import {
  GateHistory,
  ScoreBagRow,
  ScoreDecomposition,
  ScoreTimeline,
  SearchSignalRow,
  getScoreBags,
  getScoreDecomposition,
  getScoreGates,
  getScoreTimeline,
  getSearchSignal,
} from "@/lib/adminApi";
import { adminCopy, scoreComponentLabels } from "@/lib/adminVocabulary";

const COMPONENT_ORDER = [
  "search_momentum",
  "active_inventory_momentum",
  "asking_price_momentum",
  "marketplace_breadth",
  "listing_turnover_proxy",
];

export default function ScorePage() {
  const [bags, setBags] = useState<ScoreBagRow[]>([]);
  const [slug, setSlug] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<ScoreTimeline | null>(null);
  const [gates, setGates] = useState<GateHistory | null>(null);
  const [signal, setSignal] = useState<SearchSignalRow[]>([]);
  const [decomp, setDecomp] = useState<ScoreDecomposition | null>(null);

  useEffect(() => {
    getScoreBags()
      .then((data) => {
        setBags(data.bags);
        if (data.bags.length > 0) {
          setSlug((current) => current ?? data.bags[0].slug);
        }
      })
      .catch(() => setBags([]));
  }, []);

  const loadBag = useCallback((bagSlug: string) => {
    getScoreTimeline(bagSlug)
      .then((data) => {
        setTimeline(data);
        const lastScored = [...data.timeline].reverse().find((row) => row.scored);
        if (lastScored) {
          getScoreDecomposition(bagSlug, lastScored.date).then(setDecomp).catch(() => setDecomp(null));
        } else {
          setDecomp(null);
        }
      })
      .catch(() => setTimeline(null));
    getScoreGates(bagSlug).then(setGates).catch(() => setGates(null));
    getSearchSignal(bagSlug).then((data) => setSignal(data.search_signal)).catch(() => setSignal([]));
  }, []);

  useEffect(() => {
    if (slug) {
      loadBag(slug);
    }
  }, [slug, loadBag]);

  const latestGate = gates?.gate_history.at(-1) ?? null;

  return (
    <div className="adminStack">
      <header className="adminHeader">
        <h1>{adminCopy.score}</h1>
        <span className="adminChip">{adminCopy.shadowMode}</span>
      </header>

      <div className="adminChipRow" role="tablist" aria-label="Bags">
        {bags.map((bag) => (
          <button
            key={bag.slug}
            type="button"
            className={bag.slug === slug ? "adminChip adminChipActive" : "adminChip"}
            onClick={() => setSlug(bag.slug)}
          >
            {bag.slug}
            {" — "}
            {bag.classification ?? adminCopy.notScored}
          </button>
        ))}
      </div>

      {timeline ? (
        <section className="adminTool adminStack">
          <div className="adminHeader">
            <h2>{timeline.model_name}</h2>
            <span className="adminMuted">{adminCopy.timeline}</span>
          </div>
          <table className="adminTable">
            <thead>
              <tr>
                <th>Date</th>
                <th>{adminCopy.rawScore}</th>
                <th>{adminCopy.smoothed}</th>
                <th>{adminCopy.publicationTrack}</th>
                <th>{adminCopy.classification}</th>
                <th>{adminCopy.direction}</th>
                <th>{adminCopy.confidence}</th>
              </tr>
            </thead>
            <tbody>
              {timeline.timeline.map((row) => (
                <tr key={row.date}>
                  <td>{row.date}</td>
                  {row.scored ? (
                    <>
                      <td>{fmt(row.raw_score)}</td>
                      <td>{fmt(row.smoothed_score)}</td>
                      <td>{fmt(row.publication_value)}</td>
                      <td>{row.classification}</td>
                      <td>{row.direction}</td>
                      <td>{fmt(row.confidence)}</td>
                    </>
                  ) : (
                    <td colSpan={6} className="adminMuted">
                      {adminCopy.notScored} — {row.unscored_reason}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : (
        <p className="adminMuted">{adminCopy.noRows}</p>
      )}

      {latestGate ? (
        <section className="adminTool adminStack">
          <h2>
            {adminCopy.components} &amp; {adminCopy.gateHistory} ({latestGate.date})
          </h2>
          <table className="adminTable">
            <thead>
              <tr>
                <th>{adminCopy.components}</th>
                <th>{adminCopy.eligible}</th>
                <th>{adminCopy.weight}</th>
                <th>{adminCopy.reason}</th>
              </tr>
            </thead>
            <tbody>
              {COMPONENT_ORDER.map((key) => {
                const cell = latestGate.components[key];
                return (
                  <tr key={key} className={cell?.eligible ? undefined : "adminMuted"}>
                    <td>{scoreComponentLabels[key] ?? key}</td>
                    <td>{cell?.eligible ? "yes" : "no"}</td>
                    <td>{cell?.weight != null ? `${cell.weight}%` : "-"}</td>
                    <td>{cell?.reason ?? ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      ) : null}

      {decomp && decomp.previous_date ? (
        <section className="adminTool adminStack">
          <h2>
            {adminCopy.decomposition} ({decomp.previous_date} → {decomp.date})
          </h2>
          <table className="adminTable">
            <thead>
              <tr>
                <th>{adminCopy.components}</th>
                <th>Prev</th>
                <th>Now</th>
                <th>Δ {adminCopy.contribution}</th>
              </tr>
            </thead>
            <tbody>
              {decomp.components.map((part) => (
                <tr key={part.component}>
                  <td>{scoreComponentLabels[part.component] ?? part.component}</td>
                  <td>{part.contribution_previous.toFixed(2)}</td>
                  <td>{part.contribution_now.toFixed(2)}</td>
                  <td>{signed(part.delta)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={3}>
                  {adminCopy.rawScore} Δ {signed(decomp.raw_delta)} · sum of parts {signed(decomp.decomposition_sum)}
                </td>
                <td>{Math.abs(decomp.raw_delta - decomp.decomposition_sum) < 0.02 ? "✓" : "≠"}</td>
              </tr>
            </tfoot>
          </table>
        </section>
      ) : null}

      {signal.length > 0 ? (
        <section className="adminTool adminStack">
          <h2>{adminCopy.searchSignal}</h2>
          <table className="adminTable">
            <thead>
              <tr>
                <th>Week</th>
                <th>{adminCopy.bucket}</th>
                <th>Slope 8w</th>
                <th>Slope 4w</th>
                <th>Alias agrees</th>
                <th>Low volume</th>
              </tr>
            </thead>
            <tbody>
              {signal.map((row) => (
                <tr key={row.week_start}>
                  <td>{row.week_start}</td>
                  <td>{row.bucket}</td>
                  <td>{fmt(row.slope_8w)}</td>
                  <td>{fmt(row.slope_4w)}</td>
                  <td>{row.alias_agrees == null ? "-" : row.alias_agrees ? "yes" : "no"}</td>
                  <td>{row.low_volume ? "yes" : "no"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
    </div>
  );
}

function fmt(value: number | null): string {
  return value == null ? "-" : value.toFixed(2);
}

function signed(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}
