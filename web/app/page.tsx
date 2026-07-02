import { metricDisplayVocabulary } from "@/lib/vocabulary";

const pilotBags = [
  "Chloé Paddington",
  "Balenciaga City",
  "Fendi Baguette",
  "Dior Saddle",
  "Louis Vuitton Pochette Accessoires",
];

export default function Home() {
  return (
    <main className="shell">
      <section className="hero" aria-labelledby="page-title">
        <div className="heroCopy">
          <p className="eyebrow">Phase 0 foundations</p>
          <h1 id="page-title">Covetability</h1>
          <p className="lede">
            Active-market intelligence for the five-bag pilot, with contract-first language,
            condition-banded ranges, and score shadow mode from day one.
          </p>
        </div>
        <div className="statusPanel" aria-label="Phase 0 system status">
          <div>
            <span>API</span>
            <strong>/health</strong>
          </div>
          <div>
            <span>Catalog</span>
            <strong>5 models</strong>
          </div>
          <div>
            <span>Score</span>
            <strong>Shadow mode</strong>
          </div>
        </div>
      </section>

      <section className="grid" aria-label="Pilot bags">
        {pilotBags.map((bag) => (
          <article className="bagCard" key={bag}>
            <span className="cardLabel">Tracking setup</span>
            <h2>{bag}</h2>
            <p>Seeded aliases, variants, exclusions, and initial queries.</p>
          </article>
        ))}
      </section>

      <section className="contractBand" aria-label="Metric language">
        <h2>Contract Vocabulary</h2>
        <dl>
          <div>
            <dt>Price range label</dt>
            <dd>{metricDisplayVocabulary.typicalAskingRange}</dd>
          </div>
          <div>
            <dt>Lifecycle label</dt>
            <dd>{metricDisplayVocabulary.listingTurnover}</dd>
          </div>
          <div>
            <dt>Search label</dt>
            <dd>{metricDisplayVocabulary.searchInterest}</dd>
          </div>
        </dl>
      </section>
    </main>
  );
}
