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
