import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import {
  AuctionRecordsTable,
  BandRangeCard,
  Chip,
  ColorwayBars,
  ContextNotes,
  HistoryCharts,
  ObservationList,
  SiteFooter,
  SiteHeader,
  StatCard,
  VariantTable,
  monthLabel,
  trackingSinceLabel,
} from "@/app/components/MarketComponents";
import { CovetListForm } from "@/app/components/CovetListForm";
import { VariantDetail } from "@/app/components/VariantDetail";
import {
  getAuctionRecords,
  getBag,
  getContextNotes,
  getHistory,
  getListings,
  getMarket,
} from "@/lib/publicApi";
import { metricDisplayVocabulary } from "@/lib/vocabulary";

export const dynamic = "force-dynamic";

type PageProps = {
  params: Promise<{ slug: string }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  try {
    const bag = await getBag(slug);
    return {
      title: `${bag.brand.name} ${bag.model_name} - Typical asking range & market activity | Covetability`,
      description:
        bag.editorial.summary ??
        `Condition-banded market activity for ${bag.brand.name} ${bag.model_name}.`,
    };
  } catch {
    return {
      title: "Bag not found | Covetability",
    };
  }
}

export default async function BagPage({ params }: PageProps) {
  const { slug } = await params;
  let data: Awaited<ReturnType<typeof loadBagPage>>;
  try {
    data = await loadBagPage(slug);
  } catch {
    notFound();
  }
  const { bag, market, history, listings, auctionRecords, contextNotes } = data;
  const nonSeparateVariants = bag.variants.filter((variant) => !variant.is_separate_market);
  const productName = `${bag.brand.name} ${bag.model_name}`;
  const jsonLd = [
    {
      "@context": "https://schema.org",
      "@type": "Product",
      name: productName,
      brand: { "@type": "Brand", name: bag.brand.name },
      description: bag.editorial.summary,
      url: `/bags/${bag.slug}`,
    },
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      itemListElement: [
        { "@type": "ListItem", position: 1, name: "Covetability", item: "/" },
        { "@type": "ListItem", position: 2, name: productName, item: `/bags/${bag.slug}` },
      ],
    },
  ];

  return (
    <>
      <SiteHeader />
      <main className="page-wrap">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <section className="bagHero">
          <div>
            <span className="kicker-lg">
              <Link href={`/brands/${bag.brand.slug}`}>{bag.brand.name}</Link>
            </span>
            <h1>{bag.model_name}</h1>
            <p>{bag.editorial.summary}</p>
            <div className="chipRow">
              {bag.era ? <Chip on>{bag.era}</Chip> : null}
              {bag.tracking_since ? <Chip>{trackingSinceLabel(bag.tracking_since)}</Chip> : null}
              {nonSeparateVariants.map((variant) => (
                <Chip key={variant.id}>{variant.name}</Chip>
              ))}
            </div>
          </div>
          <div className="statgrid">
            <StatCard
              label="Active matched"
              value={String(market.totals.active_matched_listing_count)}
              caption={market.as_of_date ? `as of ${market.as_of_date}` : undefined}
            />
            <StatCard
              label="Priced bands"
              value={`${market.totals.bands_with_sufficient_data}/6`}
              caption={`${market.window_days}-day window`}
            />
            <StatCard
              label="Colorways"
              value={String(bag.variants.length)}
              caption={`${listings.total} listings shown`}
            />
          </div>
        </section>

        <VariantDetail
          slug={bag.slug}
          modelName={bag.model_name}
          bands={market.bands}
          variants={market.variants}
          history={history}
          listings={listings.items}
          score={market.score}
          observations={market.observations}
        />

        <section className="contentSection" aria-labelledby="pay-heading">
          <div className="sectionHeader">
            <h2 id="pay-heading">What should I pay</h2>
            <Link className="muted" href={`/bags/${bag.slug}/conditions`}>
              By condition &rsaquo;
            </Link>
          </div>
          <div className="rangeGrid">
            {market.bands.map((band) => (
              <BandRangeCard band={band} key={band.band} />
            ))}
          </div>
          {market.variants.length ? (
            <>
              <div className="hr" />
              <div className="sectionHeader">
                <h2>Colorways</h2>
                <span className="muted">{metricDisplayVocabulary.colorwayAttributionBestEffort}</span>
              </div>
              <div className="variant2col">
                <VariantTable variants={market.variants} history={history} />
                <ColorwayBars variants={market.variants} />
              </div>
            </>
          ) : null}
        </section>

        <section className="contentSection" aria-labelledby="covet-list-heading">
          <div className="sectionHeader">
            <h2 id="covet-list-heading">{metricDisplayVocabulary.covetList}</h2>
            <span className="muted">Weekly digest preview scaffold</span>
          </div>
          <CovetListForm slug={bag.slug} />
        </section>

        <section className="contentSection" aria-labelledby="moving-heading">
          <div className="sectionHeader">
            <h2 id="moving-heading">Movement &amp; context</h2>
            <span className="muted">
              {history.days_of_history} {metricDisplayVocabulary.daysOfTracking}
            </span>
          </div>
          <ObservationList observations={market.observations} daysOfHistory={history.days_of_history} />
          <ContextNotes notes={contextNotes.items} />
        </section>

        <section className="contentSection" aria-labelledby="auction-heading">
          <div className="sectionHeader">
            <h2 id="auction-heading">{metricDisplayVocabulary.notableAuctionResults}</h2>
            <span className="muted">Auction records are context anchors only.</span>
          </div>
          <AuctionRecordsTable records={auctionRecords.items} />
        </section>

        <section className="contentSection" aria-labelledby="history-heading">
          <div className="sectionHeader">
            <h2 id="history-heading">History</h2>
            <span className="muted">
              {history.days_of_history} {metricDisplayVocabulary.daysOfTracking}
            </span>
          </div>
          <HistoryCharts history={history} />
        </section>

        <section className="contentSection" aria-labelledby="editorial-heading">
          <div className="sectionHeader">
            <h2 id="editorial-heading">Editorial</h2>
            <span className="muted">
              {bag.tracking_since ? `Tracking began ${monthLabel(bag.tracking_since)}` : ""}
            </span>
          </div>
          <div className="editorialProse">
            <p>{bag.editorial.history}</p>
            <p>{bag.editorial.condition_notes}</p>
          </div>
        </section>
      </main>
      <SiteFooter trackingSince={bag.tracking_since} />
    </>
  );
}

async function loadBagPage(slug: string) {
  const [bag, market, history, listings, auctionRecords, contextNotes] = await Promise.all([
    getBag(slug),
    getMarket(slug),
    getHistory(slug),
    getListings(slug, 200),
    getAuctionRecords(slug),
    getContextNotes(slug),
  ]);
  return { bag, market, history, listings, auctionRecords, contextNotes };
}
