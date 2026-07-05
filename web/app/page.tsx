import Link from "next/link";

import { SiteFooter, SiteHeader, StatCard } from "@/app/components/MarketComponents";
import { getBags, type BagSummary } from "@/lib/publicApi";
import { metricDisplayVocabulary } from "@/lib/vocabulary";

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

export default async function Home() {
  const bags = await loadBags();
  return (
    <>
      <SiteHeader />
      <main className="page-wrap">
        <section className="homeHero">
          <div>
            <span className="kicker-lg">Five-bag pilot</span>
            <h1>Covetability</h1>
            <p>
              Active-market intelligence for vintage designer handbags, with condition-banded
              asking ranges and score shadow mode from day one.
            </p>
          </div>
          <div className="statgrid">
            <StatCard label="Catalog" value={String(bags.length)} caption="pilot models" />
            <StatCard label="Display rule" value="6" caption="condition bands" />
            <StatCard label="Score" value="Shadow" caption="pre-publication" />
          </div>
        </section>

        <section className="contentSection">
          <div className="sectionHeader">
            <h2>Catalog</h2>
            <span className="muted">{metricDisplayVocabulary.typicalAskingRange}</span>
          </div>
          <div className="rangeGrid">
            {bags.map((bag) => (
              <Link className="rangeCard" href={`/bags/${bag.slug}`} key={bag.slug}>
                <span className="kicker">{bag.brand.name}</span>
                <strong className="rangePrice">{bag.model_name}</strong>
                <span className="muted">{bag.editorial_summary}</span>
              </Link>
            ))}
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}

async function loadBags() {
  try {
    const response = await getBags();
    return response.items;
  } catch {
    return fallbackBags;
  }
}
