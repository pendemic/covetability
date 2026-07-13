import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { SiteFooter, SiteHeader } from "@/app/components/MarketComponents";
import { getBag, getListings, getMarket, type MarketResponse } from "@/lib/publicApi";
import { authLabelDisplay, conditionBandLabels, metricDisplayVocabulary } from "@/lib/vocabulary";

export const dynamic = "force-dynamic";

type PageProps = {
  params: Promise<{ slug: string }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  try {
    const bag = await getBag(slug);
    return {
      title: `${bag.brand.name} ${bag.model_name} - Typical asking by condition | Covetability`,
      description: `Condition-banded typical asking ranges and authentication labels for ${bag.brand.name} ${bag.model_name}.`,
    };
  } catch {
    return { title: "Conditions not found | Covetability" };
  }
}

const AUTH_ORDER = [
  "platform_authenticated",
  "marketplace_authentication_program",
  "seller_claim_only",
  "authentication_status_unknown",
] as const;

const AUTH_DESCRIPTIONS: Record<(typeof AUTH_ORDER)[number], string> = {
  platform_authenticated: "Marketplace inspected and verified the item.",
  marketplace_authentication_program: "Enrolled in a program; not necessarily inspected.",
  seller_claim_only: "Authenticity asserted by the seller alone.",
  authentication_status_unknown: "No authentication signal available.",
};

function modelRange(market: MarketResponse): { low: number; high: number } | null {
  const ok = market.bands.filter((band) => band.status === "ok");
  const lows = ok.map((band) => Number(band.p25_asking_price ?? band.median_asking_price));
  const highs = ok.map((band) => Number(band.p75_asking_price ?? band.median_asking_price));
  if (lows.length === 0) return null;
  return { low: Math.min(...lows), high: Math.max(...highs) };
}

export default async function ConditionsPage({ params }: PageProps) {
  const { slug } = await params;
  let data: Awaited<ReturnType<typeof loadConditions>>;
  try {
    data = await loadConditions(slug);
  } catch {
    notFound();
  }
  const { bag, market, listings } = data;
  const range = modelRange(market);
  const totalActive = market.bands.reduce((sum, band) => sum + band.active_listing_count, 0);

  const authCounts = new Map<string, number>();
  for (const listing of listings.items) {
    authCounts.set(listing.auth_label, (authCounts.get(listing.auth_label) ?? 0) + 1);
  }

  return (
    <>
      <SiteHeader />
      <main className="page-wrap">
        <section className="brandHero">
          <span className="kicker-lg">
            <Link href={`/bags/${bag.slug}`}>{`‹ ${bag.brand.name} ${bag.model_name}`}</Link>
          </span>
          <h1>Typical asking by condition</h1>
          <p>
            {range
              ? `Model-wide range $${range.low.toLocaleString()} – $${range.high.toLocaleString()} · `
              : ""}
            asking prices only, winsorized · bands below the minimum are shown but not priced.
          </p>
        </section>

        <section className="contentSection">
          <div className="bandTable">
            <div className="bandTableHead">
              <span>Band</span>
              <span>Listings</span>
              <span>Share of active</span>
              <span className="alignRight">{metricDisplayVocabulary.typicalAskingRange}</span>
            </div>
            {market.bands.map((band) => {
              const priced = band.status === "ok";
              const share = totalActive ? (band.active_listing_count / totalActive) * 100 : 0;
              const listingsText = priced
                ? `${band.active_listing_count} listings`
                : band.active_listing_count > 0
                  ? `${band.active_listing_count} listing${band.active_listing_count === 1 ? "" : "s"} · below minimum`
                  : "Not priced";
              const askingText = priced
                ? `$${Number(band.p25_asking_price).toLocaleString()} – $${Number(band.p75_asking_price).toLocaleString()}`
                : band.active_listing_count > 0
                  ? "Below minimum"
                  : "No active listings";
              return (
                <div className={priced ? "bandRow" : "bandRow off"} key={band.band}>
                  <span className="bandName">{conditionBandLabels[band.band]}</span>
                  <span className="muted bandListings">{listingsText}</span>
                  <span className="bandShare">
                    <span className="bandShareTrack">
                      <span className="bandShareFill" style={{ width: `${share}%` }} />
                    </span>
                  </span>
                  <span className="bandAsking alignRight">{askingText}</span>
                </div>
              );
            })}
          </div>
        </section>

        <section className="contentSection">
          <div className="sectionHeader">
            <h2>Authentication labels</h2>
          </div>
          <p className="muted authDisclosure">{metricDisplayVocabulary.authenticationDisclosure}</p>
          <div className="authGrid">
            {AUTH_ORDER.map((label) => (
              <div className={`authCard auth-${label}`} key={label}>
                <div className="authCardTop">
                  <strong>{authLabelDisplay[label]}</strong>
                  <span className="muted">{authCounts.get(label) ?? 0} listings</span>
                </div>
                <span className="muted">{AUTH_DESCRIPTIONS[label]}</span>
              </div>
            ))}
          </div>
        </section>
      </main>
      <SiteFooter trackingSince={bag.tracking_since} />
    </>
  );
}

async function loadConditions(slug: string) {
  const [bag, market, listings] = await Promise.all([
    getBag(slug),
    getMarket(slug),
    getListings(slug),
  ]);
  return { bag, market, listings };
}
