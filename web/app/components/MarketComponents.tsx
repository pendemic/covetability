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
  scoreClassificationLabels,
} from "@/lib/vocabulary";

export { SiteHeader } from "./SiteHeader";

export function SiteFooter({ trackingSince }: { trackingSince?: string | null }) {
  return (
    <footer className="siteFooter">
      <p>{metricDisplayVocabulary.authenticationDisclosure}</p>
      {trackingSince ? <p>{trackingSinceLabel(trackingSince)}</p> : null}
      <Link href="/methodology">Methodology</Link>
      <Link href="/affiliate-disclosure">Partner link disclosure</Link>
      <Link href="/privacy">Privacy</Link>
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

export function pickMedian(bands: BandRange[]): number | null {
  const priced = bands.find((band) => band.status === "ok" && band.median_asking_price);
  return priced?.median_asking_price ? Number(priced.median_asking_price) : null;
}

export function VolumeBars({
  title,
  values,
  delta,
}: {
  title: string;
  values: number[];
  delta?: string | null;
}) {
  const max = Math.max(1, ...values);
  return (
    <figure className="chartCard">
      <figcaption>
        {title}
        <ChartDelta delta={delta} />
      </figcaption>
      <div className="volumeBars" aria-hidden="true">
        {values.map((value, index) => (
          <div className="volumeBar" key={index} style={{ height: `${(value / max) * 100}%` }} />
        ))}
      </div>
    </figure>
  );
}

export function Sparkline({ values }: { values: Array<number | null> }) {
  const path = buildChartPath(values, 6, 40, 40);
  if (!path.line) {
    return <span className="sparkEmpty" aria-hidden="true" />;
  }
  return (
    <svg className="sparkline" viewBox="0 0 1000 300" preserveAspectRatio="none" aria-hidden="true">
      <path className="sparkPath" d={path.line} />
    </svg>
  );
}

// 2A model overview: colorways ranked by typical asking, with a search-interest
// sparkline and activity count. Per the v1 data contract, no per-variant score is
// shown - only the model carries a Covetability Score.
export function VariantTable({
  variants,
  history,
}: {
  variants: MarketResponse["variants"];
  history: HistoryResponse;
}) {
  if (variants.length === 0) {
    return null;
  }
  const seriesFor = (id: number) => history.variants.find((entry) => entry.variant_id === id);
  return (
    <div className="variantTable">
      <div className="variantTableHead">
        <span>Colorway</span>
        <span className="alignRight">Typical asking</span>
        <span>Search interest</span>
        <span className="alignRight">Active</span>
      </div>
      {variants.map((variant) => {
        const median = pickMedian(variant.bands);
        const series = seriesFor(variant.variant_id);
        const priced = series?.series.find((entry) => entry.points.some((point) => point.median != null));
        const values = priced ? priced.points.map((point) => (point.median == null ? null : Number(point.median))) : [];
        const active = variant.bands.reduce((sum, band) => sum + band.active_listing_count, 0);
        return (
          <div className="variantTableRow" key={variant.variant_id}>
            <span className="variantName">{variant.name}</span>
            <span className="alignRight variantMedian">{median == null ? "—" : `$${median.toLocaleString()}`}</span>
            <Sparkline values={values} />
            <span className="alignRight muted">{active}</span>
          </div>
        );
      })}
    </div>
  );
}

export function ColorwayBars({ variants }: { variants: MarketResponse["variants"] }) {
  const rows = variants
    .map((variant) => ({ name: variant.name, median: pickMedian(variant.bands) ?? 0 }))
    .filter((row) => row.median > 0)
    .sort((a, b) => b.median - a.median);
  if (rows.length === 0) {
    return null;
  }
  const max = Math.max(...rows.map((row) => row.median));
  return (
    <div className="colorwayBars">
      <span className="kicker">Typical asking by colorway</span>
      {rows.map((row) => (
        <div className="colorwayBar" key={row.name}>
          <span className="colorwayName">{row.name}</span>
          <div className="colorwayTrack">
            <div className="colorwayFill" style={{ width: `${(row.median / max) * 100}%` }} />
          </div>
          <span className="colorwayVal">${row.median.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

export function ScoreRing({ score }: { score: MarketResponse["score"] }) {
  const month = monthLabel(score.tracking_since);
  const value = score.status === "published" ? Math.max(0, Math.min(100, score.value ?? 0)) : null;
  const classification =
    score.classification && score.classification in scoreClassificationLabels
      ? scoreClassificationLabels[score.classification as keyof typeof scoreClassificationLabels]
      : null;
  const dash = value == null ? 0 : (value / 100) * scoreRingCircumference;
  return (
    <div className="scorePanel">
      <svg
        viewBox="0 0 140 140"
        role="img"
        aria-label={value == null ? metricDisplayVocabulary.notYetScored : `${metricDisplayVocabulary.score} ${value}`}
      >
        <circle className="scoreTrack" cx="70" cy="70" r="52" />
        <circle
          className="scoreProgress"
          cx="70"
          cy="70"
          r="52"
          strokeDasharray={`${dash} ${scoreRingCircumference}`}
        />
        {value == null ? null : (
          <text className="scoreSvgText" x="70" y="78" textAnchor="middle">
            {value}
          </text>
        )}
      </svg>
      <div>
        <span className="kicker">{metricDisplayVocabulary.score}</span>
        {value == null ? (
          <h2>{notYetScoredTrackingSince(month)}</h2>
        ) : (
          <>
            <h2>
              {value} - {classification}
            </h2>
            <p className="muted">
              Confidence: {score.confidence_label ?? metricDisplayVocabulary.confidenceLow}
              {score.direction ? ` - ${score.direction}` : ""}
            </p>
          </>
        )}
      </div>
    </div>
  );
}

export function ScoreBreakdown({ score }: { score: MarketResponse["score"] }) {
  if (score.status !== "published") {
    return null;
  }
  return (
    <div className="scoreBreakdown">
      <div className="scoreSegments" aria-hidden="true">
        {score.components.map((component) => (
          <span
            className={component.eligible ? "scoreSegment" : "scoreSegment off"}
            key={component.key}
            style={{ flexGrow: Number(component.contribution ?? component.weight_used ?? 0) || 1 }}
          />
        ))}
      </div>
      <div className="tableWrap">
        <table className="scoreTable">
          <thead>
            <tr>
              <th>Component</th>
              <th>Score</th>
              <th>Weight</th>
              <th>Contribution</th>
              <th>Gate</th>
            </tr>
          </thead>
          <tbody>
            {score.components.map((component) => (
              <tr className={component.eligible ? "" : "mutedRow"} key={component.key}>
                <td>{component.key.replaceAll("_", " ")}</td>
                <td>{component.value ?? ""}</td>
                <td>{component.weight_used ?? "0.00"}%</td>
                <td>{component.contribution ?? "0.00"}</td>
                <td>{component.eligible ? "Eligible" : component.reason ?? "Ineligible"}</td>
              </tr>
            ))}
          </tbody>
        </table>
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
            <th>Seller</th>
            <th>Location</th>
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
              <td>{listing.seller_id ?? ""}</td>
              <td>{listing.item_location ?? ""}</td>
              <td>{listing.verdict ? <VerdictChip verdict={listing.verdict} /> : null}</td>
              <td>
                <span className="mono">{formatDateTime(listing.last_observed)}</span>
                {listing.item_url ? (
                  <a
                    className="outboundLink"
                    data-analytics-event="outbound_click"
                    href={listing.item_url}
                    rel="nofollow noopener"
                    target="_blank"
                  >
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

// Words stripped from listing titles so the name reduces to ~brand + model.
// A bag's own model tokens are protected (see `protect`) so model names that are
// themselves colours/materials/types survive (Saddle, Baguette, Vitello, Nappa,
// Pochette, Bowling, City, Spy, Jackie, …).
const TITLE_STRIP_WORDS = new Set<string>([
  // colours
  "black", "white", "brown", "tan", "beige", "red", "blue", "navy", "green", "olive",
  "khaki", "pink", "blush", "nude", "grey", "gray", "silver", "gold", "golden", "cream",
  "ivory", "burgundy", "wine", "maroon", "bordeaux", "camel", "cognac", "whiskey", "caramel",
  "chocolate", "taupe", "purple", "violet", "lavender", "yellow", "orange", "coral", "teal",
  "turquoise", "mint", "mustard", "rose", "fuchsia", "magenta", "charcoal", "ecru",
  "multicolor", "multicolour", "tricolor", "colour", "color",
  // colour / finish modifiers
  "light", "dark", "deep", "pale", "bright", "soft", "dusty", "metallic", "matte", "glossy",
  "shiny", "textured", "smooth", "quilted", "embossed", "distressed",
  // materials / finishes
  "leather", "suede", "calfskin", "lambskin", "calf", "nappa", "vitello", "canvas", "nylon",
  "patent", "grained", "grain", "pebbled", "pebble", "saffiano", "denim", "fabric", "python",
  "snakeskin", "crocodile", "croc", "alligator", "ostrich", "exotic", "jacquard", "monogram",
  "monogramme", "coated", "textile", "wool", "felt", "straw", "raffia", "velvet", "satin",
  "epi", "damier", "empreinte", "caviar", "lame", "sequin", "tweed", "trotter", "oblique",
  "zucca", "zucchino", "guccissima", "chevre", "agneau", "cuir",
  // stopwords / connectors that get orphaned after stripping
  "the", "from", "with", "and", "for", "of", "in", "by", "on", "at", "this",
  // silhouettes / types
  "satchel", "tote", "hobo", "handbag", "bag", "shoulder", "crossbody", "clutch", "bucket",
  "backpack", "purse", "pouch", "flap", "handle", "hand", "boston", "bowling", "doctor",
  "messenger", "duffle", "duffel", "wristlet",
  // sizes
  "mini", "small", "medium", "large", "oversized", "xl",
  // generic marketing filler
  "authentic", "authenticity", "auth", "genuine", "real", "guaranteed", "rare", "find", "iconic",
  "boho", "vintage", "designer", "luxury", "luxe", "stunning", "gorgeous", "beautiful",
  "excellent", "preowned", "preloved", "used", "new", "nwt", "nwot", "women", "womens",
  "woman", "ladies", "mens", "unisex", "shipping", "free", "fast",
  // condition / accessory abbreviations
  "nm", "euc", "vguc", "guc", "dust", "dustbag", "extra", "tags", "size", "double",
  // brand-specific colour / material names
  "vernis", "amarante", "azur", "ebene", "vachetta", "toile",
]);

function normalizeToken(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

// Reduce a raw eBay-style title to a clean name (~brand + model), stripping
// colour / year / material / type / size / marketing noise. `protect` is the
// bag's brand+model text, whose tokens are always kept. Falls back to the
// original if cleaning would leave too little.
export function cleanListingTitle(title: string, protect = ""): string {
  const keep = new Set(
    protect
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .filter(Boolean),
  );
  const pre = title
    .replace(/\([^)]*\)/g, " ") // parenthetical SKUs / notes
    .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{2705}\u{2764}\u{FE0F}]/gu, "")
    .replace(/\$\s?\d[\d,.]*/g, " ") // prices
    .replace(/\b(19|20)\d{2}\b/g, " ") // years
    .replace(/\by2k\b/gi, " ")
    .replace(/\b\d{1,4}0s\b/gi, " ") // decades: 90s, 2000s
    .replace(/\b\d+(\.\d+)?\s?(cm|mm|in|inch|inches|")\b/gi, " ") // dimensions
    .replace(/\bl@@k\b/gi, " ")
    .replace(/[|•*/]+/g, " ");
  const kept = pre
    .split(/\s+/)
    .filter(Boolean)
    .filter((token) => {
      const norm = normalizeToken(token);
      if (!norm) return false;
      if (keep.has(norm)) return true;
      return !TITLE_STRIP_WORDS.has(norm);
    });
  const result = kept
    .join(" ")
    .replace(/\s{2,}/g, " ")
    .replace(/^[\s\-–—,.]+|[\s\-–—,.]+$/g, "")
    .trim();
  return result.length >= 3 ? result : title.trim();
}

function CompactVerdict({ verdict }: { verdict: ListingItem["verdict"] }) {
  if (!verdict) return <span className="muted">—</span>;
  const glyph = verdict.label === "below" ? "▼" : verdict.label === "above" ? "▲" : "≈";
  const word =
    verdict.label === "below" ? "below" : verdict.label === "above" ? "above" : "near";
  return (
    <span className={`readChip ${verdict.label}`}>
      {glyph} {Math.abs(Number(verdict.percent_diff)).toFixed(0)}% {word}
    </span>
  );
}

// Descriptive "Listings · <name>" table for the detail view: thumbnail + parsed
// listing name, price, condition, marketplace, seller, authentication and a
// price read. Hovering a row enlarges the eBay image.
export function CompactListings({
  listings,
  total,
  viewAllHref,
  protect = "",
  limit = 8,
}: {
  listings: ListingItem[];
  total: number;
  viewAllHref?: string;
  protect?: string;
  limit?: number;
}) {
  if (listings.length === 0) {
    return <p className="muted">No active matched listings are available.</p>;
  }
  const rows = [...listings]
    .sort((a, b) => Number(a.total_price ?? a.price) - Number(b.total_price ?? b.price))
    .slice(0, limit);
  return (
    <div className="listingGrid">
      <div className="listingGridHead">
        <span />
        <span>Listing</span>
        <span>Price</span>
        <span>Condition</span>
        <span>Marketplace</span>
        <span>Seller</span>
        <span>Authentication</span>
        <span>Read</span>
      </div>
      {rows.map((listing) => {
        const subtitleParts = [listing.variant?.name, listing.item_location].filter(Boolean);
        const row = (
          <>
            <span
              className="listingThumb"
              style={listing.image_url ? { backgroundImage: `url("${listing.image_url}")` } : undefined}
              aria-hidden="true"
            />
            <span className="listingName">
              <strong>{cleanListingTitle(listing.title, protect)}</strong>
              {subtitleParts.length ? (
                <span className="muted">{subtitleParts.join(" · ")}</span>
              ) : null}
            </span>
            <span className="listingCol listingPriceCol mono">
              ${listing.total_price ?? listing.price}
              {listing.shipping_price ? <span className="muted"> +ship</span> : null}
            </span>
            <span className="listingCol">
              {listing.condition_band ? conditionBandLabels[listing.condition_band] : "Unbanded"}
              <span className="muted listingSub">{listing.condition_confidence} conf.</span>
            </span>
            <span className="listingCol listingMkt">{listing.source}</span>
            <span className="listingCol muted">{listing.seller_id ?? "—"}</span>
            <span className="listingCol">
              <AuthLabelBadge label={listing.auth_label} />
            </span>
            <span className="listingCol">
              <CompactVerdict verdict={listing.verdict} />
            </span>
            {listing.image_url ? (
              <span
                className="listingPreview"
                style={{ backgroundImage: `url("${listing.image_url}")` }}
                aria-hidden="true"
              />
            ) : null}
          </>
        );
        return listing.item_url ? (
          <a
            className="listingRow"
            data-analytics-event="outbound_click"
            href={listing.item_url}
            key={listing.id}
            rel="nofollow noopener"
            target="_blank"
          >
            {row}
          </a>
        ) : (
          <div className="listingRow" key={listing.id}>
            {row}
          </div>
        );
      })}
      {viewAllHref && total > rows.length ? (
        <Link className="compactViewAll" href={viewAllHref}>
          View all {total} &rarr;
        </Link>
      ) : total > rows.length ? (
        <span className="compactViewAll muted">{total - rows.length} more active listings</span>
      ) : null}
    </div>
  );
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

export function ChartDelta({ delta }: { delta?: string | null }) {
  if (!delta) return null;
  const up = !delta.startsWith("-");
  return <span className={up ? "chartDelta up" : "chartDelta down"}>{up ? "▲" : "▼"} {delta}</span>;
}

export function LineChart({
  title,
  points,
  delta,
}: {
  title: string;
  points: Array<{ date: string; value: number | null }>;
  delta?: string | null;
}) {
  const path = buildChartPath(points.map((point) => point.value));
  return (
    <figure className="chartCard">
      <figcaption>
        {title}
        <ChartDelta delta={delta} />
      </figcaption>
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
                  <a
                    className="outboundLink"
                    data-analytics-event="outbound_click"
                    href={record.listing_url}
                    rel="nofollow noopener"
                    target="_blank"
                  >
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
