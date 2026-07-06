from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.contract import AuthLabel, ConditionBand, ConditionConfidence, VariantKind

PriceStatus = Literal["ok", "insufficient_data"]


class BrandSummary(BaseModel):
    slug: str
    name: str


class BagListItem(BaseModel):
    slug: str
    model_name: str
    brand: BrandSummary
    era: str | None
    tracking_since: str | None
    editorial_summary: str | None


class BagListResponse(BaseModel):
    items: list[BagListItem]
    total: int


class VariantSummary(BaseModel):
    id: int
    name: str
    kind: VariantKind
    attribution_confidence: str | None
    is_separate_market: bool


class BagDetailResponse(BaseModel):
    slug: str
    model_name: str
    brand: BrandSummary
    era: str | None
    tracking_since: str | None
    editorial: dict[str, str | None]
    variants: list[VariantSummary]


class BandRange(BaseModel):
    band: ConditionBand
    status: PriceStatus
    active_listing_count: int = Field(ge=0)
    matched_listing_count: int = Field(ge=0)
    median_asking_price: str | None = None
    p25_asking_price: str | None = None
    p75_asking_price: str | None = None
    median_total_price: str | None = None

    @model_validator(mode="after")
    def validate_price_gate(self) -> BandRange:
        asking_prices = [
            self.median_asking_price,
            self.p25_asking_price,
            self.p75_asking_price,
        ]
        all_prices = [*asking_prices, self.median_total_price]
        if self.status == "insufficient_data" and any(value is not None for value in all_prices):
            raise ValueError("insufficient_data bands cannot expose price fields")
        if self.status == "ok" and any(value is None for value in asking_prices):
            raise ValueError("ok bands require asking price fields")
        return self


class MarketVariant(BaseModel):
    variant_id: int
    name: str
    bands: list[BandRange]


class MarketTotals(BaseModel):
    active_matched_listing_count: int
    bands_with_sufficient_data: int


class ScoreComponent(BaseModel):
    key: str
    state: str
    eligible: bool | None = None
    weight_used: str | None = None
    value: str | None = None
    contribution: str | None = None
    reason: str | None = None


class ScoreBlock(BaseModel):
    status: Literal["not_yet_scored", "published"]
    tracking_since: str | None
    value: int | None = None
    classification: str | None = None
    direction: str | None = None
    confidence_label: Literal["Low", "Moderate", "High"] | None = None
    confidence_raw: str | None = None
    components: list[ScoreComponent]


class Observation(BaseModel):
    metric: str
    window_days: int
    band: ConditionBand | None = None
    from_value: str | int | None = None
    to_value: str | int | None = None
    percent_change: str | None = None
    magnitude: str
    sentence: str


class MarketResponse(BaseModel):
    slug: str
    as_of_date: str | None
    window_days: int
    tracking_since: str | None
    totals: MarketTotals
    bands: list[BandRange]
    variants: list[MarketVariant]
    score: ScoreBlock
    observations: list[Observation]


class DiscoveryBagItem(BaseModel):
    slug: str
    model_name: str
    brand: BrandSummary
    tracking_since: str | None
    editorial_summary: str | None
    metric_label: str
    metric_value: str
    caption: str | None = None
    status: PriceStatus


class DiscoverModule(BaseModel):
    key: Literal["featured", "rising_asking_interest", "under_the_radar"]
    title: str
    description: str
    items: list[DiscoveryBagItem]


class DiscoverResponse(BaseModel):
    as_of_date: str | None
    modules: list[DiscoverModule]


class HistoryPoint(BaseModel):
    date: str
    median: str | None
    p25: str | None
    p75: str | None
    active_listing_count: int


class HistorySeries(BaseModel):
    band: ConditionBand
    points: list[HistoryPoint]


class ActivityPoint(BaseModel):
    date: str
    active_listing_count: int
    new_listing_count: int


class HistoryVariant(BaseModel):
    variant_id: int
    name: str
    series: list[HistorySeries]


class HistoryResponse(BaseModel):
    slug: str
    tracking_since: str | None
    days_of_history: int
    series: list[HistorySeries]
    activity: list[ActivityPoint]
    variants: list[HistoryVariant]


class ListingVariant(BaseModel):
    id: int
    name: str
    is_separate_market: bool


class ListingVerdict(BaseModel):
    percent_diff: str
    band: ConditionBand
    label: Literal["below", "near", "above"]


class ListingItem(BaseModel):
    id: int
    title: str
    source: str
    price: str
    currency: str
    shipping_price: str | None
    total_price: str | None
    condition_band: ConditionBand | None
    condition_confidence: ConditionConfidence
    auth_label: AuthLabel
    match_confidence: str | None
    variant: ListingVariant | None
    seller_id: str | None
    item_location: str | None
    item_url: str | None
    last_observed: str
    verdict: ListingVerdict | None


class ListingsResponse(BaseModel):
    slug: str
    items: list[ListingItem]
    total: int
