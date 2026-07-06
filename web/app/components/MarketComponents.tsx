import Link from "next/link";

import { buildChartPath, scoreRingCircumference } from "@/lib/charts";
import type {
  AuctionRecord,
  BandRange,
  ContextNote,
  HistoryResponse,
  ListingItem,
  MarketResponse,
} from "@/lib/publicApi";
import {
  authLabelDisplay,
  conditionBandLabels,
  metricDisplayVocabulary,
  notYetScoredTrackingSince,
} from "@/lib/vocabulary";

export function SiteHeader() {
  return (
    <header className="topbar">
      <Link className="wordmark" href="/">
        Covetability
      </Link>
      <nav className="nav" aria-label="Public">
        <Link href="/methodology">Methodology</Link>
        <Link href="/admin">Admin</Link>
      </nav>
    </header>
  );
}

export function SiteFooter({ trackingSince }: { trackingSince?: string | null }) {
  return (
    <footer className="siteFooter">
      <p>{metricDisplayVocabulary.authenticationDisclosure}</p>
      {trackingSince ? <p>{trackingSinceLabel(trackingSince)}</p> : null}
      <Link href="/methodology">Methodology</Link>
    </footer>
  );
}

export function StatCard({
  label,
  value,
  caption,
}: {
  label: string;
  value: string;
  caption?: string;
}) {
  return (
    <div className="statcard">
      <span className="kicker">{label}</span>
      <strong className="statnum">{value}</strong>
      {caption ? <span className="muted">{caption}</span> : null}
    </div>
  );
}

export function Chip({ children, on = false }: { children: React.ReactNode; on?: boolean }) {
  return <span className={on ? "chip on" : "chip"}>{children}</span>;
}

export function Badge({ children }: { children: React.ReactNode }) {
  return <span className="badge">{children}</span>;
}

export function Tag({ children }: { children: React.ReactNode }) {
  return <span className="tag">{children}</span>;
}

export function BandRangeCard({ band }: { band: BandRange }) {
  const label = conditionBandLabels[band.band];
  return (
    <article className="rangeCard">
      <div>
        <span className="kicker">{`${metricDisplayVocabulary.typicalAskingRange} \u2014 ${label}`}</span>
        {band.status === "ok" ? (
          <strong className="rangePrice">
            ${band.p25_asking_price}-${band.p75_asking_price}
          </strong>
        ) : (
          <strong className="rangePrice mutedRange">{metricDisplayVocabulary.insufficientReliableData}</strong>
        )}
      </div>
      <p className="muted">
        {band.matched_listing_count} matched listings, {band.active_listing_count} active
      </p>
    </article>
  );
}

export function VariantPanel({
  variant,
}: {
  variant: MarketResponse["variants"][number];
}) {
  const okBands = variant.bands.filter((band) => band.status === "ok").length;
  return (
    <article className="variantPanel">
      <div className="rowBetween">
        <h3>{variant.name}</h3>
        <Badge>{metricDisplayVocabulary.modelLevelScore}</Badge>
      </div>
      <div className="variantBands">
        {variant.bands.map((band) => (
          <span key={band.band} className={band.status === "ok" ? "miniBand priced" : "miniBand"}>
            {conditionBandLabels[band.band]} - {band.matched_listing_count}
          </span>
        ))}
      </div>
      <p className="muted">{okBands} condition bands have public ranges.</p>
    </article>
  );
}

export function ScoreRing({ trackingSince }: { trackingSince: string | null }) {
  const month = monthLabel(trackingSince);
  return (
    <div className="scorePanel">
      <svg viewBox="0 0 140 140" role="img" aria-label={metricDisplayVocabulary.notYetScored}>
        <circle className="scoreTrack" cx="70" cy="70" r="52" />
        <circle
          className="scoreProgress"
          cx="70"
          cy="70"
          r="52"
          strokeDasharray={`0 ${scoreRingCircumference}`}
        />
      </svg>
      <div>
        <span className="kicker">{metricDisplayVocabulary.score}</span>
        <h2>{notYetScoredTrackingSince(month)}</h2>
      </div>
    </div>
  );
}

export function ObservationList({
  observations,
  daysOfHistory,
}: {
  observations: MarketResponse["observations"];
  daysOfHistory: number;
}) {
  if (observations.length < 3) {
    return (
      <div className="note-card">
        Too little history to report movement - {daysOfHistory} {metricDisplayVocabulary.daysOfTracking}.
      </div>
    );
  }
  return (
    <ul className="observationList">
      {observations.map((observation) => (
        <li key={`${observation.metric}-${observation.band ?? "model"}`}>{observation.sentence}</li>
      ))}
    </ul>
  );
}

export function ListingsTable({ listings }: { listings: ListingItem[] }) {
  if (listings.length === 0) {
    return <p className="muted">No active matched listings are available.</p>;
  }
  return (
    <div className="tableWrap">
      <table className="listingsTable">
        <thead>
          <tr>
            <th>Listing</th>
            <th>Band</th>
            <th>Price</th>
            <th>Authentication label</th>
            <th>Read</th>
            <th>Last verified</th>
          </tr>
        </thead>
        <tbody>
          {listings.map((listing) => (
            <tr className="row-hover" key={listing.id}>
              <td>
                <strong>{listing.title}</strong>
                {listing.variant ? <span className="muted"> {listing.variant.name}</span> : null}
              </td>
              <td>{listing.condition_band ? conditionBandLabels[listing.condition_band] : "Unbanded"}</td>
              <td>${listing.total_price ?? listing.price}</td>
              <td>
                <AuthLabelBadge label={listing.auth_label} />
              </td>
              <td>{listing.verdict ? <VerdictChip verdict={listing.verdict} /> : null}</td>
              <td>
                <span className="mono">{formatDateTime(listing.last_observed)}</span>
                {listing.item_url ? (
                  <a className="outboundLink" href={listing.item_url} rel="nofollow noopener" target="_blank">
                    Open listing
                  </a>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function AuthLabelBadge({ label }: { label: string }) {
  const display = authLabelDisplay[label as keyof typeof authLabelDisplay] ?? label;
  return <Badge>{display}</Badge>;
}

export function VerdictChip({ verdict }: { verdict: NonNullable<ListingItem["verdict"]> }) {
  const phrase =
    verdict.label === "above"
      ? metricDisplayVocabulary.aboveTypicalAsking
      : verdict.label === "below"
        ? metricDisplayVocabulary.belowTypicalAsking
        : metricDisplayVocabulary.typicalAskingMatch;
  return (
    <span className={`verdictChip ${verdict.label}`}>
      about {Math.abs(Number(verdict.percent_diff)).toFixed(1)}% {phrase} for{" "}
      {conditionBandLabels[verdict.band]} condition.
    </span>
  );
}

export function LineChart({
  title,
  points,
}: {
  title: string;
  points: Array<{ date: string; value: number | null }>;
}) {
  const path = buildChartPath(points.map((point) => point.value));
  return (
    <figure className="chartCard">
      <figcaption>{title}</figcaption>
      <svg viewBox="0 0 1000 300" preserveAspectRatio="none" aria-hidden="true">
        {path.area ? <path className="chartArea" d={path.area} /> : null}
        {path.line ? <path className="chartLine" d={path.line} /> : null}
      </svg>
      <div className="chartDates">
        <span>{points[0]?.date ?? ""}</span>
        <span>{points.at(-1)?.date ?? ""}</span>
      </div>
    </figure>
  );
}

export function HistoryCharts({ history }: { history: HistoryResponse }) {
  const priced = history.series.filter((series) => series.points.some((point) => point.median != null));
  if (priced.length === 0) {
    return <p className="muted">No priced condition-band history yet.</p>;
  }
  return (
    <div className="historyGrid">
      {priced.map((series) => (
        <LineChart
          key={series.band}
          title={conditionBandLabels[series.band]}
          points={series.points.map((point) => ({
            date: point.date.slice(5),
            value: point.median == null ? null : Number(point.median),
          }))}
        />
      ))}
      <LineChart
        title="Active matched listings"
        points={history.activity.map((point) => ({
          date: point.date.slice(5),
          value: point.active_listing_count,
        }))}
      />
    </div>
  );
}

export function AuctionRecordsTable({ records }: { records: AuctionRecord[] }) {
  if (records.length === 0) {
    return <p className="muted">No auction records have been entered yet.</p>;
  }
  return (
    <div className="tableWrap">
      <table className="listingsTable">
        <thead>
          <tr>
            <th>Source</th>
            <th>Observed</th>
            <th>Condition</th>
            <th>Price</th>
            <th>Context</th>
          </tr>
        </thead>
        <tbody>
          {records.map((record) => (
            <tr className="row-hover" key={record.id}>
              <td>{record.source}</td>
              <td>{record.observed_at ? formatDateTime(record.observed_at) : ""}</td>
              <td>{record.condition_band ? conditionBandLabels[record.condition_band] : ""}</td>
              <td>
                {record.price ? `$${record.price} ${record.currency}` : ""}
                {record.confirmed ? <span className="badge inlineBadge">confirmed</span> : null}
              </td>
              <td>
                {record.notes ? <span>{record.notes}</span> : null}
                {record.listing_url ? (
                  <a className="outboundLink" href={record.listing_url} rel="nofollow noopener" target="_blank">
                    Open record
                  </a>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ContextNotes({ notes }: { notes: ContextNote[] }) {
  if (notes.length === 0) {
    return null;
  }
  return (
    <div className="contextNotes">
      {notes.map((note) => (
        <article className="note-card" key={note.id}>
          <span className="kicker">{note.note_date}</span>
          <p>{note.body}</p>
        </article>
      ))}
    </div>
  );
}

export function trackingSinceLabel(value: string) {
  return `${metricDisplayVocabulary.trackingSince} ${monthLabel(value)}`;
}

export function monthLabel(value: string | null) {
  if (!value) {
    return "July 2026";
  }
  return new Date(`${value}T00:00:00Z`).toLocaleString("en", { month: "long", year: "numeric" });
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
