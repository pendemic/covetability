import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import {
  ObservationList,
  ScoreBreakdown,
  ScoreRing,
  SiteFooter,
  SiteHeader,
} from "@/app/components/MarketComponents";
import { getBag, getHistory, getMarket, type MarketResponse } from "@/lib/publicApi";
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
      title: `${bag.brand.name} ${bag.model_name} - ${metricDisplayVocabulary.score} signals | Covetability`,
      description: `How the ${metricDisplayVocabulary.score} for ${bag.brand.name} ${bag.model_name} is composed, made transparent.`,
    };
  } catch {
    return { title: "Signals not found | Covetability" };
  }
}

type MomentumWindow = { window_days: number; label: string; value: string; metric: string };

// Momentum windows = observed deltas, one card per (metric × lookback window)
// actually present in the observation set. These describe only what already
// happened — no predictive/lead-indicator claims (D1).
function momentumWindows(observations: MarketResponse["observations"]): MomentumWindow[] {
  return observations
    .filter((obs) => obs.percent_change != null)
    .map((obs) => ({
      window_days: obs.window_days,
      label: `${obs.window_days}-day`,
      value: `${Number(obs.percent_change) >= 0 ? "+" : ""}${obs.percent_change}%`,
      metric: obs.metric.replaceAll("_", " "),
    }))
    .sort((a, b) => a.window_days - b.window_days)
    .slice(0, 4);
}

export default async function SignalsPage({ params }: PageProps) {
  const { slug } = await params;
  let data: Awaited<ReturnType<typeof loadSignals>>;
  try {
    data = await loadSignals(slug);
  } catch {
    notFound();
  }
  const { bag, market, history } = data;
  const published = market.score.status === "published";
  const windows = momentumWindows(market.observations);

  return (
    <>
      <SiteHeader />
      <main className="page-wrap">
        <section className="brandHero">
          <div className="vdCrumb">
            <Link className="kicker" href={`/bags/${bag.slug}`}>{`‹ ${bag.model_name}`}</Link>
            <span className="vdTag">Signals</span>
          </div>
          <h1>Signals</h1>
          <p>The {metricDisplayVocabulary.score}, made transparent — every component, weight, and contribution.</p>
        </section>

        <section className="contentSection">
          <ScoreRing score={market.score} />
          <p className="muted signalsIdentity">{metricDisplayVocabulary.scoreIdentityStatement}</p>
        </section>

        <div className="signalsGrid">
          <section className="contentSection signalsBreakdown">
            <div className="sectionHeader">
              <h2>Score breakdown</h2>
              <span className="muted">{metricDisplayVocabulary.modelLevelScore}</span>
            </div>
            {published ? (
              <ScoreBreakdown score={market.score} />
            ) : (
              <div className="componentGrid">
                {market.score.components.map((component) => (
                  <div className="componentPanel" key={component.key}>
                    <strong>{component.key.replaceAll("_", " ")}</strong>
                    <span className="muted">
                      {component.state === "insufficient_stable_search_data"
                        ? metricDisplayVocabulary.insufficientSearchData
                        : "Not yet computed"}
                    </span>
                  </div>
                ))}
              </div>
            )}
            <p className="muted signalsExclusions">{metricDisplayVocabulary.scoreExclusions}</p>
          </section>

          <aside className="contentSection signalsSide">
            <div className="sectionHeader">
              <h2>Momentum windows</h2>
              <span className="muted">observed change</span>
            </div>
            {windows.length ? (
              <div className="momentumWindows">
                {windows.map((win, index) => (
                  <div className="momentumCell" key={`${win.metric}-${win.window_days}-${index}`}>
                    <span className="kicker">{win.label}</span>
                    <strong className="mono">{win.value}</strong>
                    <span className="muted">{win.metric}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted">
                Too little history for windowed movement — {history.days_of_history}{" "}
                {metricDisplayVocabulary.daysOfTracking}.
              </p>
            )}

            <div className="sectionHeader signalsWhy">
              <h2>Why it&apos;s moving</h2>
            </div>
            <ObservationList observations={market.observations} daysOfHistory={history.days_of_history} />
          </aside>
        </div>
      </main>
      <SiteFooter trackingSince={bag.tracking_since} />
    </>
  );
}

async function loadSignals(slug: string) {
  const [bag, market, history] = await Promise.all([
    getBag(slug),
    getMarket(slug),
    getHistory(slug),
  ]);
  return { bag, market, history };
}
