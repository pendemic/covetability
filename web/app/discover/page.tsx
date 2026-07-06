import Link from "next/link";

import { SiteFooter, SiteHeader } from "@/app/components/MarketComponents";
import { getDiscover, searchBags, type BagSummary, type DiscoverResponse } from "@/lib/publicApi";

export const dynamic = "force-dynamic";

type DiscoverProps = {
  searchParams?: Promise<{ q?: string }>;
};

const fallbackDiscover: DiscoverResponse = {
  as_of_date: null,
  modules: [
    {
      key: "featured",
      title: "Featured",
      description: "Pilot bags with public condition-banded tracking.",
      items: [],
    },
    {
      key: "rising_asking_interest",
      title: "Rising asking interest",
      description: "Recent increases in active matched listings.",
      items: [],
    },
    {
      key: "under_the_radar",
      title: "Under the radar",
      description: "Low active inventory or limited public range coverage.",
      items: [],
    },
  ],
};

export default async function DiscoverPage({ searchParams }: DiscoverProps) {
  const params = await searchParams;
  const query = params?.q?.trim() ?? "";
  const [discover, matches] = await Promise.all([loadDiscover(), query ? loadSearch(query) : []]);
  return (
    <>
      <SiteHeader />
      <main className="page-wrap">
        <section className="homeHero">
          <div>
            <span className="kicker-lg">Discover</span>
            <h1>Catalog signals</h1>
            <p>
              Score-free modules built from condition-banded aggregates, active listings, and
              editorial catalog entries.
            </p>
            <form className="searchForm" action="/discover" method="get">
              <input
                aria-label="Search catalog"
                defaultValue={query}
                name="q"
                placeholder="Search brand, model, or alias"
                type="search"
              />
              <button className="btn" type="submit">
                Search
              </button>
            </form>
          </div>
          <div className="note-card">
            <span className="kicker">Latest aggregate day</span>
            <strong className="discoverDate">{discover.as_of_date ?? "Pending"}</strong>
            <p>Composite score output remains internal during shadow mode.</p>
          </div>
        </section>

        {query ? (
          <section className="contentSection">
            <div className="sectionHeader">
              <h2>Catalog matches</h2>
              <span className="muted">{matches.length} matches</span>
            </div>
            <div className="rangeGrid">
              {matches.map((bag) => (
                <BagSearchCard key={bag.slug} bag={bag} />
              ))}
            </div>
          </section>
        ) : null}

        {discover.modules.map((module) => (
          <section className="contentSection" key={module.key}>
            <div className="sectionHeader">
              <h2>{module.title}</h2>
              <span className="muted">{module.description}</span>
            </div>
            <div className="discoverGrid">
              {module.items.map((item) => (
                <Link className="rangeCard" href={`/bags/${item.slug}`} key={`${module.key}-${item.slug}`}>
                  <span className="kicker">{item.brand.name}</span>
                  <strong className="rangePrice">{item.model_name}</strong>
                  <span className="muted">{item.editorial_summary}</span>
                  <span className="discoverMetric">
                    {item.metric_label}: {item.metric_value}
                  </span>
                  {item.caption ? <span className="muted">{item.caption}</span> : null}
                </Link>
              ))}
            </div>
          </section>
        ))}
      </main>
      <SiteFooter />
    </>
  );
}

function BagSearchCard({ bag }: { bag: BagSummary }) {
  return (
    <Link className="rangeCard" href={`/bags/${bag.slug}`}>
      <span className="kicker">{bag.brand.name}</span>
      <strong className="rangePrice">{bag.model_name}</strong>
      <span className="muted">{bag.editorial_summary}</span>
    </Link>
  );
}

async function loadDiscover() {
  try {
    return await getDiscover();
  } catch {
    return fallbackDiscover;
  }
}

async function loadSearch(query: string) {
  try {
    const response = await searchBags(query);
    return response.items;
  } catch {
    return [];
  }
}
