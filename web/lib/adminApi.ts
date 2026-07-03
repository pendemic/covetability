import { conditionBands, rejectionReasons } from "@/lib/adminVocabulary";

export type RejectionReason = (typeof rejectionReasons)[number];
export type ConditionBand = (typeof conditionBands)[number];
export type Verdict = "accept" | "reject";

export type AdminListing = {
  id: number;
  marketplace_item_id: string;
  title: string;
  price: string;
  currency: string;
  shipping_price: string | null;
  shipping_currency: string | null;
  seller_id: string | null;
  condition_raw: string | null;
  candidate_query: string | null;
  candidate_bag_model_id: number | null;
  item_url: string | null;
  image_url: string | null;
  matcher: {
    status: string;
    confidence: number | null;
    matched_bag_model_id: number | null;
    matched_variant_id: number | null;
    rule_trace: RuleTrace;
  };
};

export type RuleTrace = {
  matcher_version?: string;
  normalized_title?: string;
  selected?: string | null;
  status?: string;
  suggested_rejection_reason?: string | null;
  candidates?: Array<{
    bag_slug: string;
    confidence: number;
    hits: Array<{ rule: string; term: string; weight: number }>;
    exclusions: Array<{ term: string; scope: string; reason: string; weight: number }>;
    variant?: string | null;
  }>;
};

export type BagOption = {
  id: number;
  slug: string;
  brand: string;
  model_name: string;
  variants: Array<{ id: number; name: string; kind: string; is_separate_market: boolean }>;
  color_families: string[];
};

export type Summary = {
  snapshot_runs: Array<{
    id: number;
    run_date: string;
    source: string;
    mode: string;
    status: string;
    started_at: string;
    finished_at: string | null;
    bag_counts: Record<string, { fetched?: number; unique?: number; query_errors?: unknown[] }>;
    ended_event_count: number;
    error: string | null;
  }>;
  last_match_run: {
    id: number;
    run_at: string;
    mode: string;
    matcher_version: string;
    listings_considered: number;
    status_counts: Record<string, number>;
    threshold_exceeded: boolean;
  } | null;
  match_status_by_bag: Array<{ bag_slug: string; statuses: Record<string, number> }>;
  gold_progress: Array<{ bag_slug: string; candidate_count: number; label_count: number }>;
};

export type LabelPayload = {
  marketplace_item_id: string;
  bag_model_id: number;
  verdict: Verdict;
  rejection_reason?: RejectionReason | null;
  accepted_variant_id?: number | null;
  color_family?: string | null;
  condition_band?: ConditionBand | null;
  strap_included?: boolean | null;
  lock_included?: boolean | null;
  key_included?: boolean | null;
  dustbag_included?: boolean | null;
  cards_included?: boolean | null;
  notes?: string | null;
};

async function adminFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/admin/${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (response.status === 401 && typeof window !== "undefined") {
    window.location.assign("/admin/login");
  }
  if (!response.ok) {
    throw new Error(`Admin API ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function openAdminSession(secret: string): Promise<boolean> {
  const response = await fetch("/api/admin-session", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ secret }),
  });
  return response.ok;
}

export async function closeAdminSession(): Promise<void> {
  await fetch("/api/admin-session", { method: "DELETE" });
}

export function getIngestionSummary() {
  return adminFetch<Summary>("ingestion/summary");
}

export function getCatalogBags() {
  return adminFetch<{ items: BagOption[]; total: number }>("catalog/bags");
}

export function getNextLabel(bagSlug: string, afterId?: number) {
  const query = new URLSearchParams({ bag: bagSlug });
  if (afterId !== undefined) {
    query.set("after_id", String(afterId));
  }
  return adminFetch<{ item: AdminListing | null; remaining: number }>(
    `labeling/queue/next?${query.toString()}`,
  );
}

export function submitLabel(payload: LabelPayload) {
  return adminFetch<{ id: number; status: string }>("labels", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getReviewQueue(bagSlug?: string) {
  const query = new URLSearchParams();
  if (bagSlug) {
    query.set("bag", bagSlug);
  }
  return adminFetch<{ items: AdminListing[]; total: number; limit: number; offset: number }>(
    `review/queue?${query.toString()}`,
  );
}

export function submitReviewDecision(
  listingId: number,
  payload: {
    action: "approve" | "reassign" | "reject";
    bag_model_id?: number | null;
    variant_id?: number | null;
    rejection_reason?: RejectionReason | null;
  },
) {
  return adminFetch<{ status: string; listing_id: number; gold_label_id: number }>(
    `review/${listingId}/decision`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}
