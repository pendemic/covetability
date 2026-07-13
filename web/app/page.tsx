import Link from "next/link";

import { SiteFooter, SiteHeader, Sparkline } from "@/app/components/MarketComponents";
import {
  getBags,
  getHistory,
  getMarket,
  type BagSummary,
  type HistoryResponse,
  type MarketResponse,
} from "@/lib/publicApi";
import { swatchColor } from "@/lib/swatch";
import { metricDisplayVocabulary, scoreClassificationLabels } from "@/lib/vocabulary";

export const dynamic = "force-dynamic";

const fallbackBags: BagSummary[] = [
  {
    slug: "chloe-paddington",
    model_name: "Paddington",
    brand: { slug: "chloe", name: "Chloe" },
    era: "Phoebe Philo era",
    tracking_since: "2026-07-01",
    editorial_summary: "Padlock satchel tracking is ready once fixture aggregates are available.",
  },
  {
    slug: "balenciaga-city",
    model_name: "City",
    brand: { slug: "balenciaga", name: "Balenciaga" },
    era: "Motorcycle line",
    tracking_since: "2026-07-01",
    editorial_summary: "Archive City listings are grouped separately from the Le City reissue.",
  },
  {
    slug: "fendi-baguette",
    model_name: "Baguette",
    brand: { slug: "fendi", name: "Fendi" },
    era: "1997 onward",
    tracking_since: "2026-07-01",
    editorial_summary: "Vintage Zucca, leather, and embellished examples are condition banded.",
  },
  {
    slug: "dior-saddle",
    model_name: "Saddle",
    brand: { slug: "dior", name: "Dior" },
    era: "2000 and 2018 revival",
    tracking_since: "2026-07-01",
    editorial_summary: "Vintage and modern Saddle markets are split for public panels.",
  },
  {
    slug: "louis-vuitton-pochette-accessoires",
    model_name: "Pochette Accessoires",
    brand: { slug: "louis-vuitton", name: "Louis Vuitton" },
    era: "1992 onward",
    tracking_since: "2026-07-01",
    editorial_summary: "Classic, NM, and material buckets are tracked with careful exclusions.",
  },
];

type ModelCardData = {
  bag: BagSummary;
  range: { low: number; high: number } | null;
  bandsPriced: number;
  classification: string | null;
  sparkline: Array<number | null>;
};

// Model-level typical asking series: the median of the priced-band medians per day.
function medianSeries(history: HistoryResponse): Array<number | null> {
  const byDate = new Map<string, number[]>();
  for (const series of history.series) {
    for (const point of series.points) {
      if (point.median != null) {
        const list = byDate.get(point.date) ?? [];
        list.push(Number(point.median));
        byDate.set(point.date, list);
      }
    }
  }
  return [...byDate.keys()]
    .sort()
    .map((date) => {
      const values = (byDate.get(date) ?? []).sort((a, b) => a - b);
      if (values.length === 0) return null;
      const mid = Math.floor(values.length / 2);
      return values.length % 2 ? values[mid] : (values[mid - 1] + values[mid]) / 2;
    });
}

function modelRange(market: MarketResponse): { low: number; high: number } | null {
  const ok = market.bands.filter((band) => band.status === "ok");
  const lows = ok.map((band) => Number(band.p25_asking_price ?? band.median_asking_price));
  const highs = ok.map((band) => Number(band.p75_asking_price ?? band.median_asking_price));
  if (lows.length === 0) return null;
  return { low: Math.min(...lows), high: Math.max(...highs) };
}

function classificationOf(market: MarketResponse): string | null {
  const score = market.score;
  if (score.status !== "published" || !score.classification) return null;
  return score.classification in scoreClassificationLabels
    ? scoreClassificationLabels[score.classification as keyof typeof scoreClassificationLabels]
    : null;
}

export default async function Home() {
  const { bags, cards, live } = await loadCatalog();
  return (
    <>
      <SiteHeader />
      <main className="page-wrap">
        <section className="homeHero">
          <div>
            <span className="kicker-lg">Five-bag pilot</span>
            <h1>Covetability</h1>
            <p>
              Active-market intelligence for vintage designer handbags — condition-banded asking
              ranges and a transparent {metricDisplayVocabulary.score}, in shadow mode from day one.
              An activity index, not a price estimate.
            </p>
          </div>
          <div className="homeStatRail">
            <div className="homeStatRow">
              <span className="kicker">Catalog</span>
              <strong>{bags.length}</strong>
            </div>
            <div className="homeStatRow">
              <span className="kicker">Condition bands</span>
              <strong>6</strong>
            </div>
            <div className="homeStatRow">
              <span className="kicker">Score</span>
              <span className="shadowBadge">Shadow</span>
            </div>
          </div>
        </section>

        <section className="contentSection">
          <div className="sectionHeader">
            <h2>Catalog</h2>
            <span className="muted">{metricDisplayVocabulary.typicalAskingRange} · model level</span>
          </div>
          <div className="catalogGrid">
            {cards.map((card) => (
              <Link className="modelCard" href={`/bags/${card.bag.slug}`} key={card.bag.slug}>
                <span
                  className="modelSwatch"
                  style={{ background: swatchColor(`${card.bag.brand.name} ${card.bag.model_name}`) }}
                  aria-hidden="true"
                />
                <div className="modelCardMain">
                  <div className="modelCardTop">
                    <span className="kicker">{card.bag.brand.name}</span>
                    {card.classification ? <span className="tag">{card.classification}</span> : null}
                  </div>
                  <strong className="modelCardName">{card.bag.model_name}</strong>
                  <span className="muted modelCardMeta">
                    {card.range
                      ? `$${card.range.low.toLocaleString()} – $${card.range.high.toLocaleString()}`
                      : live
                        ? "Range pending"
                        : card.bag.editorial_summary}
                    {card.range ? ` · ${card.bandsPriced}/6 bands` : ""}
                  </span>
                  {card.sparkline.length ? (
                    <div className="modelCardSpark">
                      <Sparkline values={card.sparkline} />
                    </div>
                  ) : null}
                </div>
              </Link>
            ))}
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

async function loadCatalog(): Promise<{ bags: BagSummary[]; cards: ModelCardData[]; live: boolean }> {
  let bags: BagSummary[];
  try {
    bags = (await getBags()).items;
  } catch {
    return {
      bags: fallbackBags,
      cards: fallbackBags.map((bag) => ({
        bag,
        range: null,
        bandsPriced: 0,
        classification: null,
        sparkline: [],
      })),
      live: false,
    };
  }
  const cards = await Promise.all(
    bags.map(async (bag) => {
      try {
        const [market, history] = await Promise.all([getMarket(bag.slug), getHistory(bag.slug)]);
        return {
          bag,
          range: modelRange(market),
          bandsPriced: market.totals.bands_with_sufficient_data,
          classification: classificationOf(market),
          sparkline: medianSeries(history),
        } satisfies ModelCardData;
      } catch {
        return { bag, range: null, bandsPriced: 0, classification: null, sparkline: [] };
      }
    }),
  );
  return { bags, cards, live: true };
}
