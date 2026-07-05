import { SiteFooter, SiteHeader } from "@/app/components/MarketComponents";
import { metricDisplayVocabulary } from "@/lib/vocabulary";

export const dynamic = "force-dynamic";

export default function MethodologyPage() {
  return (
    <>
      <SiteHeader />
      <main className="page-wrap">
        <section className="homeHero">
          <div>
            <span className="kicker-lg">Methodology</span>
            <h1>How Covetability reads the market</h1>
            <p>{metricDisplayVocabulary.scoreIdentityStatement}</p>
          </div>
          <div className="note-card">{metricDisplayVocabulary.scoreExclusions}</div>
        </section>

        <section className="contentSection">
          <div className="sectionHeader">
            <h2>Score components</h2>
            <span className="muted">{metricDisplayVocabulary.modelLevelScore}</span>
          </div>
          <div className="methodGrid">
            {[
              ["Search interest", metricDisplayVocabulary.insufficientSearchData],
              ["Active inventory", "Counted from accepted active listings."],
              ["Asking price momentum", "Computed only from condition bands that meet the minimum."],
              ["Marketplace breadth", "Tracks source diversity once enough data exists."],
              ["Listing turnover proxy", "Internal until relist precision is high enough."],
            ].map(([title, body]) => (
              <article className="note-card" key={title}>
                <h2>{title}</h2>
                <p>{body}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="contentSection">
          <div className="sectionHeader">
            <h2>Authentication labels</h2>
          </div>
          <p className="sectionLead">{metricDisplayVocabulary.authenticationDisclosure}</p>
          <div className="methodGrid">
            {[
              metricDisplayVocabulary.platformAuthenticated,
              metricDisplayVocabulary.marketplaceAuthenticationProgram,
              metricDisplayVocabulary.sellerClaimOnly,
              metricDisplayVocabulary.authenticationStatusUnknown,
            ].map((label) => (
              <article className="note-card" key={label}>
                {label}
              </article>
            ))}
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
