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
  brand_slug?: string;
  brand: string;
  model_name: string;
  recompute_required?: boolean;
  recompute_flagged_at?: string | null;
  variants: Array<{ id: number; name: string; kind: string; is_separate_market: boolean }>;
  color_families: string[];
};

export type CatalogBag = {
  id: number;
  slug: string;
  brand: { id: number; slug: string; name: string };
  model_name: string;
  era: string | null;
  editorial_summary: string | null;
  editorial_history: string | null;
  editorial_condition_notes: string | null;
  expected_range_note: string | null;
  initial_queries: string[];
  tracking_since: string | null;
  recompute_required: boolean;
  recompute_flagged_at: string | null;
  aliases: Array<{ id: number; alias: string; type: string }>;
  variants: Array<{
    id: number;
    name: string;
    kind: string;
    attribution_confidence: string | null;
    is_separate_market: boolean;
  }>;
  exclusions: CatalogExclusion[];
  global_exclusions: CatalogExclusion[];
};

export type CatalogExclusion = {
  id: number;
  term: string;
  scope: string;
  reason: RejectionReason;
  notes: string | null;
};

export type BagPayload = {
  slug?: string;
  brand?: { slug: string; name: string };
  model_name?: string;
  era?: string | null;
  editorial_summary?: string | null;
  editorial_history?: string | null;
  editorial_condition_notes?: string | null;
  expected_range_note?: string | null;
  initial_queries?: string[];
  tracking_since?: string | null;
};

export type EvidenceRecord = {
  id: number;
  bag_model_id: number;
  variant_id: number | null;
  source: string;
  source_type: "manual" | "user_submitted" | "auction_record";
  observed_at: string;
  entered_by: string;
  listing_url: string;
  confirmed: boolean;
  price_type: "asking" | "realized";
  price: string;
  currency: string;
  shipping_included: boolean;
  condition_raw: string | null;
  condition_band: ConditionBand;
  condition_confidence: string;
  notes: string | null;
};

export type EvidencePayload = {
  bag_model_id: number;
  variant_id?: number | null;
  source: string;
  source_type: "manual" | "user_submitted" | "auction_record";
  observed_at: string;
  entered_by: string;
  listing_url: string;
  confirmed: boolean;
  price_type: "asking" | "realized";
  price: string;
  currency: string;
  shipping_included: boolean;
  condition_raw?: string | null;
  condition_band: ConditionBand;
  condition_confidence?: string;
  notes?: string | null;
};

export type CulturalNote = {
  id: number;
  bag_model_id: number;
  note_date: string;
  body: string;
  created_by: string | null;
  created_at: string;
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

export type QualitySummary = {
  date_from: string;
  date_to: string;
  bags: Array<{
    bag_slug: string;
    band_coverage: Record<
      string,
      Record<string, { matched: number; priced: boolean; variant_id: number | null }>
    >;
    active_trend: Array<{ date: string; count: number }>;
    confidence_trend: Array<{ date: string; average: number | null }>;
    unbanded_share: number;
    variant_attribution_share: number;
    separate_market_rows: number;
  }>;
  alarms: Array<Record<string, string | number>>;
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

export type ScoreBagRow = {
  slug: string;
  model_name: string;
  latest_date: string | null;
  raw_score: number | null;
  publication_value: number | null;
  classification: string | null;
  unscored_reason: string | null;
  score_published: boolean;
  score_published_at: string | null;
};

export type ScoreTimelineRow = {
  date: string;
  raw_score: number | null;
  smoothed_score: number | null;
  publication_value: number | null;
  classification: string | null;
  direction: string | null;
  confidence: number | null;
  scored: boolean;
  unscored_reason: string | null;
  weights: Record<string, number>;
};

export type ScoreTimeline = {
  slug: string;
  model_name: string;
  published: boolean;
  published_at: string | null;
  timeline: ScoreTimelineRow[];
};

export type ScoreReadiness = {
  slug: string;
  ready: boolean;
  items: Array<{
    key: string;
    label: string;
    passed: boolean;
    detail: string;
    operator_attested: boolean;
  }>;
  material_moves: Array<{
    date: string;
    previous_date: string | null;
    smoothed_delta: number;
    notes_present: boolean;
    warnings: string[];
  }>;
};

export type ScoreDecomposition = {
  slug: string;
  date: string;
  previous_date: string | null;
  raw_now: number;
  raw_previous: number;
  raw_delta: number;
  decomposition_sum: number;
  components: Array<{
    component: string;
    contribution_now: number;
    contribution_previous: number;
    delta: number;
    value: number | null;
    eligible: boolean | null;
    reason: string | null;
  }>;
};

export type GateHistory = {
  slug: string;
  gate_history: Array<{
    date: string;
    components: Record<string, { eligible: boolean | null; reason: string | null; weight: number | null }>;
  }>;
};

export type SearchSignalRow = {
  week_start: string;
  stitched_value: number | null;
  slope_8w: number | null;
  slope_4w: number | null;
  bucket: string | null;
  alias_agrees: boolean | null;
  low_volume: boolean;
  series_length: number;
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

export function createCatalogBag(payload: Required<Pick<BagPayload, "slug" | "brand" | "model_name">> & BagPayload) {
  return adminFetch<{ id: number; slug: string }>("catalog/bags", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getCatalogBag(slug: string) {
  return adminFetch<CatalogBag>(`catalog/bags/${slug}`);
}

export function updateCatalogBag(slug: string, payload: BagPayload) {
  return adminFetch<CatalogBag>(`catalog/bags/${slug}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function addCatalogAlias(slug: string, payload: { alias: string; type: string }) {
  return adminFetch<{ id: number }>(`catalog/bags/${slug}/aliases`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteCatalogAlias(slug: string, aliasId: number) {
  return adminFetch<{ status: string }>(`catalog/bags/${slug}/aliases/${aliasId}`, {
    method: "DELETE",
  });
}

export function addCatalogVariant(
  slug: string,
  payload: { name: string; kind: string; attribution_confidence?: string | null; is_separate_market: boolean },
) {
  return adminFetch<{ id: number }>(`catalog/bags/${slug}/variants`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteCatalogVariant(slug: string, variantId: number) {
  return adminFetch<{ status: string }>(`catalog/bags/${slug}/variants/${variantId}`, {
    method: "DELETE",
  });
}

export function addCatalogExclusion(
  slug: string,
  payload: { term: string; reason: RejectionReason; notes?: string | null },
) {
  return adminFetch<{ id: number }>(`catalog/bags/${slug}/exclusions`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteCatalogExclusion(slug: string, exclusionId: number) {
  return adminFetch<{ status: string }>(`catalog/bags/${slug}/exclusions/${exclusionId}`, {
    method: "DELETE",
  });
}

export function addGlobalExclusion(payload: { term: string; reason: RejectionReason; notes?: string | null }) {
  return adminFetch<{ id: number }>("catalog/exclusions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteGlobalExclusion(exclusionId: number) {
  return adminFetch<{ status: string }>(`catalog/exclusions/${exclusionId}`, {
    method: "DELETE",
  });
}

export function getEvidenceRecords(slug: string) {
  return adminFetch<{ items: EvidenceRecord[]; total: number }>(`evidence/bags/${slug}/comps`);
}

export function addEvidenceRecord(payload: EvidencePayload) {
  return adminFetch<{ id: number }>("evidence/comps", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteEvidenceRecord(id: number) {
  return adminFetch<{ status: string }>(`evidence/comps/${id}`, {
    method: "DELETE",
  });
}

export function getCulturalNotes(slug: string) {
  return adminFetch<{ items: CulturalNote[]; total: number }>(`evidence/bags/${slug}/cultural-notes`);
}

export function addCulturalNote(
  slug: string,
  payload: { note_date: string; body: string; created_by?: string | null },
) {
  return adminFetch<{ id: number }>(`evidence/bags/${slug}/cultural-notes`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteCulturalNote(id: number) {
  return adminFetch<{ status: string }>(`evidence/cultural-notes/${id}`, {
    method: "DELETE",
  });
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

export function getQualitySummary(days = 14) {
  return adminFetch<QualitySummary>(`quality/summary?days=${days}`);
}

export function getScoreBags() {
  return adminFetch<{ bags: ScoreBagRow[]; published: boolean }>("score/bags");
}

export function getScoreTimeline(slug: string) {
  return adminFetch<ScoreTimeline>(`score/${slug}/timeline`);
}

export function getScoreReadiness(slug: string) {
  return adminFetch<ScoreReadiness>(`score/${slug}/readiness`);
}

export function publishScore(slug: string, payload: { force?: boolean; reason?: string | null } = {}) {
  return adminFetch<{ slug: string; score_published: boolean; score_published_at: string | null; forced: boolean }>(
    `score/${slug}/publish`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}

export function unpublishScore(slug: string) {
  return adminFetch<{ slug: string; score_published: boolean }>(`score/${slug}/unpublish`, {
    method: "POST",
  });
}

export function getScoreDecomposition(slug: string, date: string) {
  return adminFetch<ScoreDecomposition>(`score/${slug}/decomposition?date=${date}`);
}

export function getScoreGates(slug: string) {
  return adminFetch<GateHistory>(`score/${slug}/gates`);
}

export function getSearchSignal(slug: string) {
  return adminFetch<{ slug: string; search_signal: SearchSignalRow[] }>(`score/${slug}/search-signal`);
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
