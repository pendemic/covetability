import Link from "next/link";

import { SiteFooter, SiteHeader, Sparkline } from "@/app/components/MarketComponents";
import { getDiscover, searchBags, type BagSummary, type DiscoverResponse } from "@/lib/publicApi";
import { swatchColor } from "@/lib/swatch";
import { metricDisplayVocabulary } from "@/lib/vocabulary";

export const dynamic = "force-dynamic";

type DiscoverProps = {
  searchParams?: Promise<{ q?: string }>;
};

type Module = DiscoverResponse["modules"][number];

const fallbackDiscover: DiscoverResponse = {
  as_of_date: null,
  totals: { models_tracked: 0, active_listings: 0, median_score: null, surging_now: 0 },
  modules: [
    { key: "featured", title: "Featured", description: "Pilot bags with public tracking.", items: [] },
    { key: "fastest_rising", title: "Fastest rising", description: "Recent increases in active listings.", items: [] },
    { key: "rising_price", title: "Biggest price moves", description: "Largest 30-day asking-price moves.", items: [] },
    { key: "emerging", title: "Newly emerging", description: "Most recently tracked.", items: [] },
    { key: "cooling", title: "Losing momentum", description: "Recent declines.", items: [] },
    { key: "under_the_radar", title: "Under the radar", description: "Thin supply or limited coverage.", items: [] },
  ],
};

function moduleMap(discover: DiscoverResponse): Record<string, Module> {
  return Object.fromEntries(discover.modules.map((module) => [module.key, module]));
}

function ModuleList({ module, note }: { module?: Module; note?: string }) {
  if (!module || module.items.length === 0) {
    return <p className="muted">No models qualify right now.</p>;
  }
  return (
    <div className="discList">
      {note ? <span className="kicker discListNote">{note}</span> : null}
      {module.items.slice(0, 5).map((item) => (
        <Link className="discRow" href={`/bags/${item.slug}`} key={`${module.key}-${item.slug}`}>
          <span
            className="discDot"
            style={{ background: swatchColor(`${item.brand.name} ${item.model_name}`) }}
            aria-hidden="true"
          />
          <div className="discRowMain">
            <span className="kicker">{item.brand.name}</span>
            <strong>{item.model_name}</strong>
          </div>
          {item.sparkline && item.sparkline.length ? (
            <span className="discRowSpark">
              <Sparkline values={item.sparkline} />
            </span>
          ) : null}
          <div className="discRowMetric">
            <strong className="mono">{item.metric_value}</strong>
            {item.caption ? <span className="muted">{item.caption}</span> : null}
          </div>
        </Link>
      ))}
    </div>
  );
}

export default async function DiscoverPage({ searchParams }: DiscoverProps) {
  const params = await searchParams;
  const query = params?.q?.trim() ?? "";
  const [discover, matches] = await Promise.all([loadDiscover(), query ? loadSearch(query) : []]);
  const byKey = moduleMap(discover);
  const hero = byKey.fastest_rising?.items[0] ?? byKey.featured?.items[0];

  return (
    <>
      <SiteHeader />
      <main className="page-wrap">
        <section className="brandHero discoverHero">
          <div>
            <span className="kicker-lg">The vintage bag market · this week</span>
            <h1>Discover</h1>
            <p className="discoverLede">What&apos;s accelerating, cooling, and hiding in plain sight.</p>
          </div>
          <div className="discoverStamp">
            <span className="muted">Snapshot</span>
            <strong>{discover.as_of_date ?? "Pending"}</strong>
          </div>
        </section>

        <section className="brandStatBand discoverTotals">
          <div className="brandStat">
            <span className="kicker">Models tracked</span>
            <strong>{discover.totals.models_tracked}</strong>
          </div>
          <div className="brandStat">
            <span className="kicker">Active listings</span>
            <strong>{discover.totals.active_listings.toLocaleString()}</strong>
          </div>
          <div className="brandStat accent">
            <span className="kicker">Median {metricDisplayVocabulary.score}</span>
            <strong>{discover.totals.median_score ?? "—"}</strong>
            <span className="muted">{discover.totals.median_score == null ? "shadow mode" : "published"}</span>
          </div>
          <div className="brandStat accent">
            <span className="kicker">Surging now</span>
            <strong>{discover.totals.surging_now}</strong>
          </div>
        </section>

        {query ? (
          <section className="contentSection">
            <div className="sectionHeader">
              <h2>Catalog matches</h2>
              <span className="muted">{matches.length} matches</span>
            </div>
            <div className="discoverGrid">
              {matches.map((bag) => (
                <Link className="rangeCard" href={`/bags/${bag.slug}`} key={bag.slug}>
                  <span className="kicker">{bag.brand.name}</span>
                  <strong className="rangePrice">{bag.model_name}</strong>
                  <span className="muted">{bag.editorial_summary}</span>
                </Link>
              ))}
            </div>
          </section>
        ) : null}

        {hero ? (
          <section className="contentSection">
            <Link className="surgeCard" href={`/bags/${hero.slug}`}>
              <span
                className="surgeSwatch"
                style={{ background: swatchColor(`${hero.brand.name} ${hero.model_name}`) }}
                aria-hidden="true"
              >
                <span className="surgeSwatchTag">{hero.brand.name} {hero.model_name}</span>
              </span>
              <div className="surgeMain">
                <span className="kicker copper">Moving now</span>
                <strong className="surgeName">{hero.model_name}</strong>
                <span className="surgeMetric mono">
                  {hero.metric_label}: {hero.metric_value}
                </span>
                {hero.editorial_summary ? <p className="muted">{hero.editorial_summary}</p> : null}
                <span className="surgeLink">View profile &rarr;</span>
              </div>
            </Link>
          </section>
        ) : null}

        <section className="contentSection">
          <div className="discoverTwo">
            <div>
              <div className="sectionHeader">
                <h2>Fastest rising</h2>
                <span className="muted">30-day active</span>
              </div>
              <ModuleList module={byKey.fastest_rising} />
            </div>
            <div>
              <div className="sectionHeader">
                <h2>Biggest price moves</h2>
                <span className="muted">30-day asking</span>
              </div>
              <ModuleList module={byKey.rising_price} />
            </div>
          </div>
        </section>

        <section className="contentSection">
          <div className="discoverThree">
            <div>
              <div className="sectionHeader">
                <h2>Newly emerging</h2>
              </div>
              <ModuleList module={byKey.emerging} />
            </div>
            <div>
              <div className="sectionHeader">
                <h2>Losing momentum</h2>
              </div>
              <ModuleList module={byKey.cooling} />
            </div>
            <div>
              <div className="sectionHeader">
                <h2>Under the radar</h2>
              </div>
              <ModuleList module={byKey.under_the_radar} />
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

async function loadDiscover() {
  try {
    return await getDiscover();
  } catch {
    return fallbackDiscover;
  }
}

async function loadSearch(query: string): Promise<BagSummary[]> {
  try {
    const response = await searchBags(query);
    return response.items;
  } catch {
    return [];
  }
}
