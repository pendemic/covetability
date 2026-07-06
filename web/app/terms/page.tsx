import { SiteFooter, SiteHeader } from "@/app/components/MarketComponents";

export const metadata = {
  title: "Terms | Covetability",
};

export default function TermsPage() {
  return (
    <>
      <SiteHeader />
      <main className="page-wrap">
        <section className="contentSection legalPage">
          <span className="kicker-lg">Terms</span>
          <h1>Terms</h1>
          <p>
            Covetability presents observed asking listings, editorial context, and internal
            methodology notes for vintage handbag research. Information can change as marketplace
            listings change.
          </p>
          <p>
            The service is not an appraisal, authentication service, or price guarantee. Outbound
            marketplace links are provided for operator and reader review.
          </p>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
