import type { Metadata } from "next";
import Link from "next/link";

import { SiteFooter, SiteHeader } from "@/app/components/MarketComponents";
import {
  getBag,
  getBags,
  getMarket,
  type BagDetail,
  type MarketResponse,
} from "@/lib/publicApi";
import { metricDisplayVocabulary, scoreClassificationLabels } from "@/lib/vocabulary";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Compare bags | Covetability",
  description: "Put 2–4 tracked bags side by side on typical asking, active listings, and Covetability Score.",
};

type PageProps = {
  searchParams?: Promise<{ slugs?: string }>;
};

type Column = { bag: BagDetail; market: MarketResponse };

const MAX_POOL = 4;

function parseSlugs(raw: string | undefined): string[] {
  if (!raw) return [];
  const seen = new Set<string>();
  for (const slug of raw.split(",").map((value) => value.trim()).filter(Boolean)) {
    seen.add(slug);
  }
  return [...seen].slice(0, MAX_POOL);
}

function toggleHref(slugs: string[], slug: string): string {
  const next = slugs.includes(slug)
    ? slugs.filter((value) => value !== slug)
    : [...slugs, slug].slice(0, MAX_POOL);
  return next.length ? `/compare?slugs=${next.join(",")}` : "/compare";
}

function typicalAsking(market: MarketResponse): string {
  const medians = market.bands
    .filter((band) => band.status === "ok" && band.median_asking_price)
    .map((band) => Number(band.median_asking_price))
    .sort((a, b) => a - b);
  if (medians.length === 0) return "—";
  const mid = Math.floor(medians.length / 2);
  const value =
    medians.length % 2 ? medians[mid] : (medians[mid - 1] + medians[mid]) / 2;
  return `$${Math.round(value).toLocaleString()}`;
}

function scoreCell(market: MarketResponse): string {
  const score = market.score;
  if (score.status !== "published" || score.value == null) return "Not yet scored";
  const label =
    score.classification && score.classification in scoreClassificationLabels
      ? scoreClassificationLabels[score.classification as keyof typeof scoreClassificationLabels]
      : null;
  return label ? `${score.value} · ${label}` : String(score.value);
}

const METRIC_ROWS: Array<{ label: string; cell: (col: Column) => string }> = [
  { label: metricDisplayVocabulary.score, cell: (col) => scoreCell(col.market) },
  { label: "Confidence", cell: (col) => col.market.score.confidence_label ?? "—" },
  { label: "Typical asking", cell: (col) => typicalAsking(col.market) },
  {
    label: "Active listings",
    cell: (col) => String(col.market.totals.active_matched_listing_count),
  },
  {
    label: "Priced bands",
    cell: (col) => `${col.market.totals.bands_with_sufficient_data}/6`,
  },
  { label: "Era", cell: (col) => col.bag.era ?? "—" },
];

export default async function ComparePage({ searchParams }: PageProps) {
  const params = await searchParams;
  const slugs = parseSlugs(params?.slugs);
  const catalog = await getBags().catch(() => ({ items: [], total: 0 }));

  const columns: Column[] = (
    await Promise.all(
      slugs.map(async (slug) => {
        try {
          const [bag, market] = await Promise.all([getBag(slug), getMarket(slug)]);
          return { bag, market } satisfies Column;
        } catch {
          return null;
        }
      }),
    )
  ).filter((col): col is Column => col !== null);

  return (
    <>
      <SiteHeader />
      <main className="page-wrap">
        <section className="brandHero">
          <span className="kicker-lg">Compare</span>
          <h1>Compare bags</h1>
          <p>Pick 2–{MAX_POOL} bags — the table updates as you toggle.</p>
        </section>

        <section className="contentSection">
          <div className="compareChips">
            {catalog.items.map((bag) => {
              const on = slugs.includes(bag.slug);
              return (
                <Link
                  className={on ? "compareChip on" : "compareChip"}
                  href={toggleHref(slugs, bag.slug)}
                  key={bag.slug}
                >
                  {bag.brand.name} {bag.model_name}
                </Link>
              );
            })}
          </div>
        </section>

        {columns.length === 0 ? (
          <section className="contentSection">
            <p className="muted">Select at least one bag above to build a comparison.</p>
          </section>
        ) : (
          <section className="contentSection">
            <div className="compareWrap">
              <div
                className="compareTable"
                style={{ gridTemplateColumns: `168px repeat(${columns.length}, minmax(0, 1fr))` }}
              >
                <div className="compareCorner" />
                {columns.map((col) => (
                  <div className="compareHead" key={col.bag.slug}>
                    <span className="kicker">{col.bag.brand.name}</span>
                    <Link className="compareModel" href={`/bags/${col.bag.slug}`}>
                      {col.bag.model_name}
                    </Link>
                  </div>
                ))}

                {METRIC_ROWS.map((row) => (
                  <div className="compareRow" key={row.label} style={{ display: "contents" }}>
                    <span className="compareLabel">{row.label}</span>
                    {columns.map((col) => (
                      <span className="compareCell" key={`${row.label}-${col.bag.slug}`}>
                        {row.cell(col)}
                      </span>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}
      </main>
      <SiteFooter />
    </>
  );
}
