import { cache } from "react";

export type ConditionBand =
  | "new_or_unused"
  | "excellent"
  | "very_good"
  | "good"
  | "fair"
  | "poor";

export type BagSummary = {
  slug: string;
  model_name: string;
  brand: { slug: string; name: string };
  era: string | null;
  tracking_since: string | null;
  editorial_summary: string | null;
};

export type BagDetail = BagSummary & {
  editorial: {
    summary: string | null;
    history: string | null;
    condition_notes: string | null;
  };
  variants: Array<{
    id: number;
    name: string;
    kind: string;
    attribution_confidence: string | null;
    is_separate_market: boolean;
  }>;
};

export type BandRange = {
  band: ConditionBand;
  status: "ok" | "insufficient_data";
  active_listing_count: number;
  matched_listing_count: number;
  median_asking_price?: string;
  p25_asking_price?: string;
  p75_asking_price?: string;
  median_total_price?: string;
};

export type MarketResponse = {
  slug: string;
  as_of_date: string | null;
  window_days: number;
  tracking_since: string | null;
  totals: {
    active_matched_listing_count: number;
    bands_with_sufficient_data: number;
  };
  bands: BandRange[];
  variants: Array<{ variant_id: number; name: string; bands: BandRange[] }>;
  score: {
    status: "not_yet_scored" | "published";
    tracking_since: string | null;
    components: Array<{ key: string; state: string }>;
  };
  observations: Array<{
    metric: string;
    window_days: number;
    band: ConditionBand | null;
    from_value: string | number | null;
    to_value: string | number | null;
    percent_change: string | null;
    magnitude: string;
    sentence: string;
  }>;
};

export type HistorySeries = {
  band: ConditionBand;
  points: Array<{
    date: string;
    median: string | null;
    p25: string | null;
    p75: string | null;
    active_listing_count: number;
  }>;
};

export type HistoryResponse = {
  slug: string;
  tracking_since: string | null;
  days_of_history: number;
  series: HistorySeries[];
  activity: Array<{ date: string; active_listing_count: number; new_listing_count: number }>;
  variants: Array<{
    variant_id: number;
    name: string;
    series: HistorySeries[];
  }>;
};

export type ListingItem = {
  id: number;
  title: string;
  source: string;
  price: string;
  currency: string;
  shipping_price?: string;
  total_price?: string;
  condition_band: ConditionBand | null;
  condition_confidence: string;
  auth_label: string;
  match_confidence: string | null;
  variant: { id: number; name: string; is_separate_market: boolean } | null;
  item_url: string | null;
  last_observed: string;
  verdict: { percent_diff: string; band: ConditionBand; label: "below" | "near" | "above" } | null;
};

export type ListingsResponse = {
  slug: string;
  items: ListingItem[];
  total: number;
};

const apiBase = process.env.PIPELINE_API_URL ?? "http://localhost:8000";

async function publicFetch<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Public API ${response.status}`);
  }
  return (await response.json()) as T;
}

export const getBags = cache(async () => publicFetch<{ items: BagSummary[]; total: number }>("/bags"));

export const getBag = cache(async (slug: string) => publicFetch<BagDetail>(`/bags/${slug}`));

export const getMarket = cache(async (slug: string) => publicFetch<MarketResponse>(`/bags/${slug}/market`));

export const getHistory = cache(async (slug: string, days = 90) =>
  publicFetch<HistoryResponse>(`/bags/${slug}/history?days=${days}`),
);

export const getListings = cache(async (slug: string, limit = 50) =>
  publicFetch<ListingsResponse>(`/bags/${slug}/listings?limit=${limit}`),
);
