import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import {
  LineChart,
  SiteFooter,
  SiteHeader,
  Sparkline,
} from "@/app/components/MarketComponents";
import { getBrand, type BrandModelItem } from "@/lib/publicApi";
import { metricDisplayVocabulary, scoreClassificationLabels } from "@/lib/vocabulary";

export const dynamic = "force-dynamic";

type PageProps = {
  params: Promise<{ slug: string }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  try {
    const brand = await getBrand(slug);
    return {
      title: `${brand.name} - House market activity | Covetability`,
      description: `Condition-banded market activity across ${brand.models_tracked} tracked ${brand.name} models.`,
    };
  } catch {
    return { title: "House not found | Covetability" };
  }
}

function classificationLabel(model: BrandModelItem): string | null {
  if (!model.classification) return null;
  return model.classification in scoreClassificationLabels
    ? scoreClassificationLabels[model.classification as keyof typeof scoreClassificationLabels]
    : null;
}

export default async function BrandPage({ params }: PageProps) {
  const { slug } = await params;
  let brand: Awaited<ReturnType<typeof getBrand>>;
  try {
    brand = await getBrand(slug);
  } catch {
    notFound();
  }

  const interestPoints = brand.interest.map((point) => ({
    date: point.date.slice(5),
    value: point.active_listing_count,
  }));

  const published = brand.models.filter((model) => model.score_value != null);
  const topModel = [...published].sort((a, b) => (b.score_value ?? 0) - (a.score_value ?? 0))[0];
  const coolingModel = brand.models.find((model) => model.classification === "cooling");

  return (
    <>
      <SiteHeader />
      <main className="page-wrap">
        <section className="brandHero">
          <span className="kicker-lg">
            <Link href="/discover">Discover</Link> &rsaquo; House
          </span>
          <h1>{brand.name}</h1>
          <p>
            {brand.models_tracked} model{brand.models_tracked === 1 ? "" : "s"} tracked
            {brand.as_of_date ? ` · as of ${brand.as_of_date}` : ""}
          </p>
        </section>

        <section className="brandStatBand">
          <div className="brandStat accent">
            <span className="kicker">Avg {metricDisplayVocabulary.score}</span>
            <strong>{brand.average_published_score == null ? "—" : brand.average_published_score}</strong>
            <span className="muted">{published.length ? `${published.length} published` : "none published yet"}</span>
          </div>
          <div className="brandStat">
            <span className="kicker">Models tracked</span>
            <strong>{brand.models_tracked}</strong>
          </div>
          <div className="brandStat">
            <span className="kicker">Active listings</span>
            <strong>{brand.active_listings}</strong>
            <span className="muted">across the house</span>
          </div>
          <div className="brandStat accent">
            <span className="kicker">House momentum &middot; 90d</span>
            <strong>{brand.house_momentum_pct ?? "—"}</strong>
            <span className="muted">active change</span>
          </div>
        </section>

        <section className="brandBody">
          <div className="brandModels contentSection">
            <div className="sectionHeader">
              <h2>Models</h2>
              <span className="muted">Open a model for its full profile</span>
            </div>
            <div className="brandTable">
              <div className="brandTableHead">
                <span>Model</span>
                <span>Median asking</span>
                <span>90-day active</span>
                <span>Status</span>
              </div>
              {brand.models.map((model) => {
                const label = classificationLabel(model);
                return (
                  <Link className="brandRow" href={`/bags/${model.slug}`} key={model.slug}>
                    <span className="brandRowName">
                      <strong>{model.model_name}</strong>
                      {model.era ? <span className="muted">{model.era} &middot; {model.active_listings} listings</span> : (
                        <span className="muted">{model.active_listings} listings</span>
                      )}
                    </span>
                    <span className="mono brandRowPrice">
                      {model.median_asking_price ? `$${Number(model.median_asking_price).toLocaleString()}` : "—"}
                    </span>
                    <span className="brandRowSpark">
                      <Sparkline values={model.sparkline} />
                    </span>
                    <span className="brandRowScore">
                      {model.score_value != null ? (
                        <>
                          <strong className="mono">{model.score_value}</strong>
                          {label ? <span className="kicker">{label}</span> : null}
                        </>
                      ) : (
                        <span className="muted">Not yet scored</span>
                      )}
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>

          <aside className="brandSide">
            <div className="chartCard">
              <span className="kicker">House interest &middot; 90d</span>
              {interestPoints.length ? (
                <LineChart title="Active listings across the house" points={interestPoints} />
              ) : (
                <p className="muted">{metricDisplayVocabulary.insufficientReliableData}</p>
              )}
            </div>
            {(topModel || coolingModel) && (
              <div className="brandReadCards">
                {topModel ? (
                  <div className="brandReadCard">
                    <span className="kicker">Top model</span>
                    <strong>{topModel.model_name}</strong>
                  </div>
                ) : null}
                {coolingModel ? (
                  <div className="brandReadCard">
                    <span className="kicker">Cooling</span>
                    <strong>{coolingModel.model_name}</strong>
                  </div>
                ) : null}
              </div>
            )}
          </aside>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
