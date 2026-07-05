import Link from "next/link";

import { SiteFooter, SiteHeader } from "@/app/components/MarketComponents";

export default function BagNotFound() {
  return (
    <>
      <SiteHeader />
      <main className="page-wrap contentSection">
        <span className="kicker-lg">Missing bag</span>
        <h1 className="serif">Bag not found</h1>
        <p className="sectionLead">This pilot catalog entry is not available.</p>
        <Link className="btn" href="/">
          Back to catalog
        </Link>
      </main>
      <SiteFooter />
    </>
  );
}
