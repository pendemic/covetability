"use client";

import Link from "next/link";
import { useState } from "react";

import type { BandRange, HistoryResponse, HistorySeries, ListingItem, MarketResponse } from "@/lib/publicApi";
import { swatchColor } from "@/lib/swatch";
import { metricDisplayVocabulary } from "@/lib/vocabulary";

import { ListingsExplorer } from "./ListingsExplorer";
import {
  LineChart,
  ScoreRing,
  VolumeBars,
  pickMedian,
} from "./MarketComponents";

type View = {
  id: string | number;
  name: string;
  bands: BandRange[];
  series: HistorySeries[];
};

function rangeBounds(bands: BandRange[]): { low: number; high: number } | null {
  const priced = bands.filter((band) => band.status === "ok" && band.p25_asking_price && band.p75_asking_price);
  if (priced.length === 0) return null;
  return {
    low: Math.min(...priced.map((band) => Number(band.p25_asking_price))),
    high: Math.max(...priced.map((band) => Number(band.p75_asking_price))),
  };
}

function percentChange(values: Array<number | null>): string | null {
  const numeric = values.filter((value): value is number => value != null);
  if (numeric.length < 2 || numeric[0] === 0) return null;
  const change = ((numeric[numeric.length - 1] - numeric[0]) / numeric[0]) * 100;
  return `${change >= 0 ? "+" : ""}${change.toFixed(0)}%`;
}

// Per-date model/variant median = median across the priced bands that day.
function medianSeries(series: HistorySeries[]): Array<{ date: string; value: number | null }> {
  const byDate = new Map<string, number[]>();
  for (const band of series) {
    for (const point of band.points) {
      if (point.median != null) {
        const list = byDate.get(point.date) ?? [];
        list.push(Number(point.median));
        byDate.set(point.date, list);
      }
    }
  }
  return [...byDate.keys()].sort().map((date) => {
    const values = (byDate.get(date) ?? []).sort((a, b) => a - b);
    const mid = Math.floor(values.length / 2);
    const value = values.length === 0 ? null : values.length % 2 ? values[mid] : (values[mid - 1] + values[mid]) / 2;
    return { date: date.slice(5), value };
  });
}

function volumeSeries(series: HistorySeries[]): number[] {
  const byDate = new Map<string, number>();
  for (const band of series) {
    for (const point of band.points) {
      byDate.set(point.date, (byDate.get(point.date) ?? 0) + point.active_listing_count);
    }
  }
  return [...byDate.keys()].sort().map((date) => byDate.get(date) ?? 0);
}

// 2B detail view. Renders for every bag: model-level when there are no
// separate-market colorways, or per-colorway with chips when there are. Score
// stays model-level (D2); velocity language stays honest (D1).
export function VariantDetail({
  slug,
  modelName,
  bands,
  variants,
  history,
  listings,
  score,
  observations,
}: {
  slug: string;
  modelName: string;
  bands: MarketResponse["bands"];
  variants: MarketResponse["variants"];
  history: HistoryResponse;
  listings: ListingItem[];
  score: MarketResponse["score"];
  observations: MarketResponse["observations"];
}) {
  const hasColorways = variants.length > 0;
  const views: View[] = hasColorways
    ? variants.map((variant) => ({
        id: variant.variant_id,
        name: variant.name,
        bands: variant.bands,
        series: history.variants.find((entry) => entry.variant_id === variant.variant_id)?.series ?? [],
      }))
    : [{ id: "model", name: modelName, bands, series: history.series }];

  const okBandCount = (view: View) => view.bands.filter((band) => band.status === "ok").length;
  const defaultView = [...views].sort((a, b) => okBandCount(b) - okBandCount(a))[0];
  const [selectedId, setSelectedId] = useState<string | number>(defaultView?.id ?? "model");
  const selected = views.find((view) => view.id === selectedId) ?? views[0];

  const medianPoints = medianSeries(selected.series);
  const volumeValues = volumeSeries(selected.series);
  const searchPoints = (history.search_interest ?? []).map((point) => ({
    date: point.week_start.slice(5),
    value: point.value,
  }));

  const median = pickMedian(selected.bands);
  const activeTotal = selected.bands.reduce((sum, band) => sum + band.active_listing_count, 0);
  const okBands = selected.bands.filter((band) => band.status === "ok");
  const bounds = rangeBounds(selected.bands);
  const askingChange = percentChange(medianPoints.map((point) => point.value));
  const volumeChange = percentChange(volumeValues);
  const searchChange = percentChange(searchPoints.map((point) => point.value));

  const scopedListings = hasColorways
    ? listings.filter((listing) => listing.variant?.id === selected.id)
    : listings;
  const whyMoving = observations.filter((obs) => obs.sentence).slice(0, 2);

  return (
    <section className="contentSection vdSection" aria-labelledby="variant-detail-heading">
      <div className="vdHeader">
        <span className="vdSwatch" style={{ background: swatchColor(selected.name) }} aria-hidden="true" />
        <div className="vdHeadMain">
          <div className="vdCrumb">
            <span className="kicker">{`‹ ${modelName}`}</span>
            <span className="vdTag">{hasColorways ? "Colorway" : "Model"}</span>
          </div>
          <h2 className="vdTitle" id="variant-detail-heading">
            {selected.name}
          </h2>
          <span className="muted">
            {bounds
              ? `Typical asking range $${bounds.low.toLocaleString()} – $${bounds.high.toLocaleString()}`
              : metricDisplayVocabulary.insufficientReliableData}
          </span>
        </div>
        <div className="vdActions">
          <a className="btnGhost" href="#covet-list-heading">
            + Watch
          </a>
          <a className="btnSolid" href="#covet-list-heading">
            {metricDisplayVocabulary.covetList}
          </a>
        </div>
      </div>

      {hasColorways ? (
        <div className="vdChips">
          {views.map((view) => (
            <button
              className={view.id === selected.id ? "vdChip on" : "vdChip"}
              key={view.id}
              onClick={() => setSelectedId(view.id)}
              type="button"
            >
              <span className="vdChipDot" style={{ background: swatchColor(view.name) }} aria-hidden="true" />
              {view.name}
            </button>
          ))}
        </div>
      ) : null}

      <div className="vdStats brandStatBand">
        <div className="brandStat accent">
          <span className="kicker">Median asking</span>
          <strong>{median == null ? "—" : `$${median.toLocaleString()}`}</strong>
          <span className="muted">{askingChange ? `${askingChange} · 90d` : "latest aggregate"}</span>
        </div>
        <div className="brandStat">
          <span className="kicker">Active listings</span>
          <strong>{activeTotal}</strong>
          <span className="muted">{hasColorways ? "in this colorway" : "model-wide"}</span>
        </div>
        <div className="brandStat accent">
          <span className="kicker">{metricDisplayVocabulary.searchInterest}</span>
          <strong>{searchChange ?? "—"}</strong>
          <span className="muted">index · trailing</span>
        </div>
        <div className="brandStat">
          <span className="kicker">{metricDisplayVocabulary.typicalAskingRange}</span>
          <strong>{bounds ? `$${bounds.low.toLocaleString()}–$${bounds.high.toLocaleString()}` : "—"}</strong>
          <span className="muted">{okBands.length}/6 bands priced</span>
        </div>
      </div>

      <div className="vdBody">
        <div className="vdCharts">
          <LineChart title="Median asking price" points={medianPoints} delta={askingChange} />
          {searchPoints.length ? (
            <LineChart title="Search interest index" points={searchPoints} delta={searchChange} />
          ) : null}
          <VolumeBars title="Active listing volume" values={volumeValues} delta={volumeChange} />
        </div>
        <div className="vdSide">
          <ScoreRing score={score} />
          <Link className="vdSignalsLink" href={`/bags/${slug}/signals`}>
            {metricDisplayVocabulary.score} breakdown &rsaquo;
          </Link>
          <div className="vdMomentum">
            <span className="kicker">Momentum</span>
            {searchPoints.length ? (
              <div className="vdMomentumRow">
                <span>{metricDisplayVocabulary.searchInterest}</span>
                <span className="mono">{searchChange ?? "—"}</span>
              </div>
            ) : null}
            <div className="vdMomentumRow">
              <span>Asking price</span>
              <span className="mono">{askingChange ?? "—"}</span>
            </div>
            <div className="vdMomentumRow">
              <span>Listing volume</span>
              <span className="mono">{volumeChange ?? "—"}</span>
            </div>
          </div>
          <div className="vdWhy">
            <span className="kicker">Why it&apos;s moving</span>
            {whyMoving.length ? (
              whyMoving.map((obs) => (
                <p key={`${obs.metric}-${obs.window_days}-${obs.band ?? "model"}`}>{obs.sentence}</p>
              ))
            ) : (
              <p className="muted">Too little history to describe movement yet.</p>
            )}
          </div>
        </div>
      </div>

      <div className="vdListings">
        <div className="sectionHeader">
          <h3>
            Listings &middot; {selected.name}
          </h3>
          <span className="muted">{metricDisplayVocabulary.authenticationDisclosure}</span>
        </div>
        <ListingsExplorer listings={scopedListings} protect={modelName} />
      </div>
    </section>
  );
}
