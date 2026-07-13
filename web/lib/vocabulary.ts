export const metricDisplayVocabulary = {
  typicalAskingRange: "Typical asking range",
  listingPriceVerdict: "above typical asking",
  listingTurnover: "Listing turnover",
  listingsThatEnded: "listings that ended",
  searchInterest: "Search interest",
  score: "Covetability Score",
  notYetScored: "Not yet scored",
  confidenceLow: "Low",
  confidenceModerate: "Moderate",
  confidenceHigh: "High",
  platformAuthenticated: "Platform-authenticated",
  marketplaceAuthenticationProgram: "Marketplace authentication program",
  sellerClaimOnly: "Seller claim only",
  authenticationStatusUnknown: "Authentication status unknown",
  insufficientReliableData: "Insufficient reliable data",
  insufficientSearchData: "Insufficient stable search data",
  modelLevelScore: "model-level score",
  colorwayAttributionBestEffort: "colorway attribution is best-effort",
  belowTypicalAsking: "below typical asking",
  aboveTypicalAsking: "above typical asking",
  typicalAskingMatch: "near typical asking",
  trackingSince: "Tracking since",
  daysOfTracking: "days of tracking",
  authenticationDisclosure:
    "Covetability does not authenticate items. Labels describe marketplace programs and seller claims only.",
  notableAuctionResults: "Notable auction results",
  culturalContext: "Cultural context",
  covetList: "Covet List",
  scoreIdentityStatement:
    "The Covetability Score v0 measures observable momentum in attention, availability, and active-market pricing for a handbag model.",
  scoreExclusions:
    "It is an activity index, not a valuation. It does not measure authenticity, investment quality, confirmed resale value, likelihood of profit, fashion quality, or personal desirability.",
} as const;

export const scoreClassificationLabels = {
  dormant: "Dormant",
  cooling: "Cooling",
  stable: "Stable",
  building: "Building",
  trending: "Trending",
  surging: "Surging",
} as const;

export const conditionBandLabels = {
  new_or_unused: "New or unused",
  excellent: "Excellent",
  very_good: "Very good",
  good: "Good",
  fair: "Fair",
  poor: "Poor",
} as const;

export const authLabelDisplay = {
  platform_authenticated: metricDisplayVocabulary.platformAuthenticated,
  marketplace_authentication_program: metricDisplayVocabulary.marketplaceAuthenticationProgram,
  seller_claim_only: metricDisplayVocabulary.sellerClaimOnly,
  authentication_status_unknown: metricDisplayVocabulary.authenticationStatusUnknown,
} as const;

export function notYetScoredTrackingSince(month: string) {
  return `Not yet scored \u2014 tracking since ${month}`;
}

export const prohibitedVocabulary = [
  "market value",
  "worth",
  "valuation",
  "sold",
  "sell-through",
  "sales rate",
  "sales",
  "Authenticated",
  "demand",
  "investment",
  "appreciating",
  "ROI",
  "forecast",
  "prediction",
] as const;
