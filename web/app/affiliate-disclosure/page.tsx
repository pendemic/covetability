import { SiteFooter, SiteHeader } from "@/app/components/MarketComponents";

export const metadata = {
  title: "Partner link disclosure | Covetability",
};

export default function AffiliateDisclosurePage() {
  return (
    <>
      <SiteHeader />
      <main className="page-wrap">
        <section className="contentSection legalPage">
          <span className="kicker-lg">Disclosure</span>
          <h1>Partner link disclosure</h1>
          <p>
            Some outbound eBay links may use partner tracking. This does not change the asking
            price shown by the marketplace, the condition-band calculation, or the order of listings
            on Covetability.
          </p>
          <p>
            Covetability does not authenticate items. Labels describe marketplace programs and
            seller claims only.
          </p>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
