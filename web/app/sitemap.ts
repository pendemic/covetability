import type { MetadataRoute } from "next";

import { getBags } from "@/lib/publicApi";

const fallbackSlugs = [
  "chloe-paddington",
  "balenciaga-city",
  "fendi-baguette",
  "dior-saddle",
  "louis-vuitton-pochette-accessoires",
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
  let slugs = fallbackSlugs;
  try {
    const response = await getBags();
    slugs = response.items.map((bag) => bag.slug);
  } catch {
    slugs = fallbackSlugs;
  }
  return [
    { url: base, lastModified: new Date() },
    { url: `${base}/discover`, lastModified: new Date() },
    { url: `${base}/methodology`, lastModified: new Date() },
    { url: `${base}/affiliate-disclosure`, lastModified: new Date() },
    { url: `${base}/terms`, lastModified: new Date() },
    { url: `${base}/privacy`, lastModified: new Date() },
    ...slugs.map((slug) => ({ url: `${base}/bags/${slug}`, lastModified: new Date() })),
  ];
}
