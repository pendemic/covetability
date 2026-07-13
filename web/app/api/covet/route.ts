import { NextRequest, NextResponse } from "next/server";

import {
  getBags,
  getHistory,
  getMarket,
  type HistoryResponse,
  type MarketResponse,
} from "@/lib/publicApi";
import { scoreClassificationLabels } from "@/lib/vocabulary";

export type CovetModel = {
  slug: string;
  brand: string;
  model_name: string;
  era: string | null;
  typical: number | null;
  classification: string | null;
  bandsPriced: number;
  activeBands: number;
  sparkline: Array<number | null>;
};

function typicalAsking(market: MarketResponse): number | null {
  const medians = market.bands
    .filter((band) => band.status === "ok" && band.median_asking_price)
    .map((band) => Number(band.median_asking_price))
    .sort((a, b) => a - b);
  if (medians.length === 0) return null;
  const mid = Math.floor(medians.length / 2);
  return medians.length % 2 ? medians[mid] : (medians[mid - 1] + medians[mid]) / 2;
}

function medianSeries(history: HistoryResponse): Array<number | null> {
  const byDate = new Map<string, number[]>();
  for (const series of history.series) {
    for (const point of series.points) {
      if (point.median != null) {
        const list = byDate.get(point.date) ?? [];
        list.push(Number(point.median));
        byDate.set(point.date, list);
      }
    }
  }
  return [...byDate.keys()]
    .sort()
    .map((date) => {
      const values = (byDate.get(date) ?? []).sort((a, b) => a - b);
      if (values.length === 0) return null;
      const mid = Math.floor(values.length / 2);
      return values.length % 2 ? values[mid] : (values[mid - 1] + values[mid]) / 2;
    });
}

function classificationOf(market: MarketResponse): string | null {
  const score = market.score;
  if (score.status !== "published" || !score.classification) return null;
  return score.classification in scoreClassificationLabels
    ? scoreClassificationLabels[score.classification as keyof typeof scoreClassificationLabels]
    : null;
}

export async function GET(request: NextRequest) {
  const url = new URL(request.url);
  const wantAll = url.searchParams.get("all") === "1";
  const slugsParam = url.searchParams.get("slugs");

  let slugs: string[];
  if (wantAll) {
    try {
      slugs = (await getBags()).items.map((bag) => bag.slug);
    } catch {
      return NextResponse.json({ models: [] });
    }
  } else {
    slugs = (slugsParam ?? "").split(",").map((s) => s.trim()).filter(Boolean).slice(0, 24);
  }

  const models = (
    await Promise.all(
      slugs.map(async (slug): Promise<CovetModel | null> => {
        try {
          const [market, history] = await Promise.all([getMarket(slug), getHistory(slug)]);
          const bagBrand = slug; // brand/model resolved from market slug via bags list below
          void bagBrand;
          return {
            slug,
            brand: "",
            model_name: "",
            era: null,
            typical: typicalAsking(market),
            classification: classificationOf(market),
            bandsPriced: market.totals.bands_with_sufficient_data,
            activeBands: market.bands.filter((b) => b.active_listing_count > 0).length,
            sparkline: medianSeries(history),
          };
        } catch {
          return null;
        }
      }),
    )
  ).filter((m): m is CovetModel => m !== null);

  // Fill brand/model/era from the catalog listing in one call.
  try {
    const bags = (await getBags()).items;
    const bySlug = new Map(bags.map((bag) => [bag.slug, bag]));
    for (const model of models) {
      const bag = bySlug.get(model.slug);
      if (bag) {
        model.brand = bag.brand.name;
        model.model_name = bag.model_name;
        model.era = bag.era;
      }
    }
  } catch {
    // brand/model stay blank; client falls back to slug
  }

  return NextResponse.json({ models });
}
