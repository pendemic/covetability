import { SiteFooter, SiteHeader } from "@/app/components/MarketComponents";

export const metadata = {
  title: "Privacy | Covetability",
};

export default function PrivacyPage() {
  return (
    <>
      <SiteHeader />
      <main className="page-wrap">
        <section className="contentSection legalPage">
          <span className="kicker-lg">Privacy</span>
          <h1>Privacy</h1>
          <p>
            Covetability uses privacy-light analytics only when configured. The intended metrics are
            page depth and outbound link clicks, without cross-site cookies or personal profiles.
          </p>
          <p>
            Admin tools are protected separately and are not part of the public browsing surface.
          </p>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
