from enum import StrEnum


class ConditionBand(StrEnum):
    new_or_unused = "new_or_unused"
    excellent = "excellent"
    very_good = "very_good"
    good = "good"
    fair = "fair"
    poor = "poor"


class ConditionConfidence(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"
    indeterminate = "indeterminate"


class AuthLabel(StrEnum):
    platform_authenticated = "platform_authenticated"
    marketplace_authentication_program = "marketplace_authentication_program"
    seller_claim_only = "seller_claim_only"
    authentication_status_unknown = "authentication_status_unknown"


class RejectionReason(StrEnum):
    wrong_model = "wrong_model"
    wrong_product_category = "wrong_product_category"
    accessory_replacement_part = "accessory_replacement_part"
    replica_or_inspired = "replica_or_inspired"
    seller_misuses_model_name = "seller_misuses_model_name"
    child_mini_variant_mismatched = "child_mini_variant_mismatched"
    bundle_or_lot = "bundle_or_lot"
    wanted_to_buy = "wanted_to_buy"
    indeterminate = "indeterminate"
    duplicate_relist = "duplicate_relist"


class SourceType(StrEnum):
    api = "api"
    manual = "manual"
    user_submitted = "user_submitted"
    auction_record = "auction_record"


class PriceType(StrEnum):
    asking = "asking"
    realized = "realized"


class AliasType(StrEnum):
    alias = "alias"
    misspelling = "misspelling"
    marketplace_term = "marketplace_term"


class VariantKind(StrEnum):
    size = "size"
    color_family = "color_family"
    edition = "edition"


class ExclusionScope(StrEnum):
    global_scope = "global"
    bag = "bag"


class ListingEventType(StrEnum):
    new = "new"
    ended = "ended"
    possible_relist = "possible_relist"
    repriced = "repriced"


class IngestionMode(StrEnum):
    fixtures = "fixtures"
    live = "live"


class SnapshotRunStatus(StrEnum):
    succeeded = "succeeded"
    partial = "partial"
    failed = "failed"


class MatchStatus(StrEnum):
    pending = "pending"
    auto_accepted = "auto_accepted"
    needs_review = "needs_review"
    auto_rejected = "auto_rejected"
    human_accepted = "human_accepted"
    human_rejected = "human_rejected"


class GoldLabelVerdict(StrEnum):
    accept = "accept"
    reject = "reject"


class GoldLabelOrigin(StrEnum):
    labeling_ui = "labeling_ui"
    review_queue = "review_queue"
    fixture_seed = "fixture_seed"


class ScoreClassification(StrEnum):
    dormant = "dormant"
    cooling = "cooling"
    stable = "stable"
    building = "building"
    trending = "trending"
    surging = "surging"


class SearchBucket(StrEnum):
    strong_up = "strong_up"
    up = "up"
    flat = "flat"
    down = "down"
    strong_down = "strong_down"


class ScoreDirection(StrEnum):
    rising = "rising"
    falling = "falling"
    stable = "stable"


class TrendQueryRole(StrEnum):
    canonical = "canonical"
    alias = "alias"


MIN_LISTINGS_PER_BAND = 5
MIN_MODEL_WIDE_LISTINGS = 8
MIN_LIFECYCLE_EVENTS = 15
MATCH_AUTO_ACCEPT = 0.90
MATCH_REVIEW_FLOOR = 0.60
WINSOR_PCT = (2, 98)
RAW_RETENTION_DAYS = 90
RELIST_WINDOW_DAYS = 14
AGGREGATE_WINDOW_DAYS = 14
ENDED_AFTER_MISSED_DAYS = 2
REMATCH_DELTA_THRESHOLD = 0.15
MATCH_PRECISION_TARGET = 0.95
MATCH_RECALL_TARGET = 0.70
VARIANT_ATTRIBUTION_TARGET = 0.85
CONDITION_ACCURACY_TARGET = 0.85
PHASH_HAMMING_MAX = 6
PUBLIC_HISTORY_DEFAULT_DAYS = 90
PUBLIC_HISTORY_MAX_DAYS = 365

SCORE_BASE_WEIGHTS = {
    "search_momentum": 25,
    "active_inventory_momentum": 25,
    "asking_price_momentum": 20,
    "marketplace_breadth": 15,
    "listing_turnover_proxy": 15,
}

SCORE_WEIGHT_CEILINGS = {
    "search_momentum": 30,
    "active_inventory_momentum": 35,
    "asking_price_momentum": 25,
    "marketplace_breadth": 25,
    "listing_turnover_proxy": 20,
}

CONFIDENCE_WEIGHTS = {
    "matched_listing_count": 0.30,
    "history_length": 0.25,
    "average_match_confidence": 0.20,
    "eligible_component_count": 0.15,
    "source_count": 0.10,
}

CONFIDENCE_CAPS = {
    "history_under_90_days": 0.60,
    "one_component_excluded": 0.75,
    "two_or_more_components_excluded": 0.55,
    "model_wide_listings_under_15": 0.50,
}

SCORE_CLASSIFICATION_BOUNDS = {
    ScoreClassification.dormant: (0, 24),
    ScoreClassification.cooling: (25, 39),
    ScoreClassification.stable: (40, 54),
    ScoreClassification.building: (55, 69),
    ScoreClassification.trending: (70, 84),
    ScoreClassification.surging: (85, 100),
}

# ---------------------------------------------------------------------------
# Score v0 shadow-mode constants (Phase 5).
# Component identifiers mirror the SCORE_BASE_WEIGHTS keys. Every ladder and
# threshold below is PROVISIONAL and expected to be tuned during shadow mode
# (score-spec §3, §6, §7); shadow mode exists precisely to calibrate them.
# ---------------------------------------------------------------------------

COMPONENT_SEARCH = "search_momentum"
COMPONENT_INVENTORY = "active_inventory_momentum"
COMPONENT_PRICE = "asking_price_momentum"
COMPONENT_BREADTH = "marketplace_breadth"
COMPONENT_TURNOVER = "listing_turnover_proxy"

COMPONENT_KEYS = (
    COMPONENT_SEARCH,
    COMPONENT_INVENTORY,
    COMPONENT_PRICE,
    COMPONENT_BREADTH,
    COMPONENT_TURNOVER,
)

# Fewer than this many eligible components leaves the model unscored (score-spec §4.2).
MIN_ELIGIBLE_COMPONENTS = 3
# Overflow that cannot be placed within ceilings goes to inventory first, then breadth.
REDISTRIBUTION_OVERFLOW_ORDER = (COMPONENT_INVENTORY, COMPONENT_BREADTH)

# S — search momentum. Bucket -> 0-100 component score (score-spec §3).
SEARCH_BUCKET_SCORES = {
    SearchBucket.strong_up: 100,
    SearchBucket.up: 75,
    SearchBucket.flat: 50,
    SearchBucket.down: 25,
    SearchBucket.strong_down: 0,
}
# 8-week smoothed-slope thresholds (anchor-rescaled units per week) -> bucket.
SEARCH_SLOPE_STRONG = 2.0
SEARCH_SLOPE_MILD = 0.5
SEARCH_MIN_SERIES_WEEKS = 16
SEARCH_SMOOTHING_WEEKS = 8
SEARCH_SHORT_SLOPE_WEEKS = 4
SEARCH_LOW_VOLUME_FLOOR = 5.0  # anchor-rescaled level below which Trends volume is sub-threshold

# I — active-inventory momentum. Declining inventory scores high (scarcity pressure).
# Applied to the negated smoothed percentage change so decline maps to the top rungs.
INVENTORY_MIN_HISTORY_DAYS = 45
INVENTORY_SMOOTHING_DAYS = 7
INVENTORY_WINDOW_DAYS = 90
INVENTORY_MOMENTUM_LADDER = (
    (0.30, 100),
    (0.15, 80),
    (0.05, 65),
    (-0.05, 50),
    (-0.15, 35),
    (-0.30, 20),
)

# P — asking-price momentum. Rising condition-adjusted asking medians score high.
PRICE_SHORT_WINDOW_DAYS = 30
PRICE_LONG_WINDOW_DAYS = 90
PRICE_SHORT_LONG_WEIGHTS = (0.5, 0.5)
PRICE_MOMENTUM_LADDER = (
    (0.15, 100),
    (0.08, 80),
    (0.03, 65),
    (-0.03, 50),
    (-0.08, 35),
    (-0.15, 20),
)
# Fixed condition-band mix weights, renormalized over bands meeting the minimum
# so a mix shift toward Excellent listings cannot read as a price rise (score-spec §3).
PRICE_BAND_MIX_WEIGHTS = {
    ConditionBand.new_or_unused: 0.10,
    ConditionBand.excellent: 0.25,
    ConditionBand.very_good: 0.30,
    ConditionBand.good: 0.20,
    ConditionBand.fair: 0.10,
    ConditionBand.poor: 0.05,
}
PRICE_MAX_UNUSABLE_CONDITION_SHARE = 0.40
PRICE_REPRICING_MIN_INTERVAL_DAYS = 14
# Divergence guard: P strong-positive while S and I flat/negative for N consecutive weeks.
PRICE_DIVERGENCE_HALVE_WEEKS = 4
PRICE_DIVERGENCE_EXCLUDE_WEEKS = 8
PRICE_DIVERGENCE_STRONG_THRESHOLD = 65  # component value treated as "strongly positive"

# B — marketplace breadth. Distinct valid sources in trailing 30 days, log-scaled.
BREADTH_WINDOW_DAYS = 30
BREADTH_LADDER = {0: 0, 1: 20, 2: 45, 3: 65, 4: 80}
BREADTH_LADDER_MAX_SCORE = 100  # 5+ sources

# T — listing-turnover proxy. Experimental; launches ineligible until relist
# precision is validated on a gold sample (score-spec §4.1).
TURNOVER_WINDOW_DAYS = 90
RELIST_PRECISION_TARGET = 0.90
TURNOVER_DEFAULT_INELIGIBLE_REASON = "relist precision unvalidated"
TURNOVER_MOMENTUM_LADDER = (
    (0.30, 100),
    (0.15, 80),
    (0.05, 65),
    (-0.05, 50),
    (-0.15, 35),
    (-0.30, 20),
)

# Confidence display bands and history cap threshold (score-spec §5).
CONFIDENCE_HISTORY_CAP_DAYS = 90
CONFIDENCE_LOW_MATCHED_LISTINGS = 15
CONFIDENCE_MATCHED_LISTING_FULL = 40  # matched-listing count that saturates its factor
CONFIDENCE_HISTORY_FULL_DAYS = 180  # history length that saturates its factor
CONFIDENCE_SOURCE_FULL = 5

# Smoothing, publication threshold, direction (score-spec §7).
SCORE_EMA_SPAN_DAYS = 7
PUBLICATION_MOVE_THRESHOLD = 2.0
DIRECTION_WINDOW_DAYS = 30
DIRECTION_STABLE_SLOPE = 0.05  # published-track points/day treated as "stable"

# Search-signal stability gate (score-spec §6).
STABILITY_FLIP_RATE_MAX = 0.25
STABILITY_SLOPE_CHANGE_EXEMPTION = 1.5  # x trailing std of the 8-week slope
STABILITY_REPRODUCIBILITY_MIN_TRIALS = 20
STABILITY_REPRODUCIBILITY_MIN_SHARE = 0.90
STABILITY_ALIAS_AGREEMENT_MIN = 0.75
STABILITY_WINDOW_ROBUSTNESS_MIN = 0.70
STABILITY_BAGS_REQUIRED = 4  # of 5 pilot bags must pass per-bag stability
SEARCH_WEIGHT_FULL = 30
SEARCH_WEIGHT_BASE = 25
SEARCH_WEIGHT_DEMOTED = 15
