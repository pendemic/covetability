from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EbayModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Money(EbayModel):
    value: Decimal
    currency: str


class Seller(EbayModel):
    username: str | None = None


class Image(EbayModel):
    image_url: str | None = Field(default=None, alias="imageUrl")


class ShippingOption(EbayModel):
    shipping_cost: Money | None = Field(default=None, alias="shippingCost")
    shipping_cost_type: str | None = Field(default=None, alias="shippingCostType")


class ItemSummary(EbayModel):
    item_id: str = Field(alias="itemId")
    title: str
    price: Money
    item_web_url: str | None = Field(default=None, alias="itemWebUrl")
    seller: Seller | None = None
    condition: str | None = None
    shipping_options: list[ShippingOption] = Field(default_factory=list, alias="shippingOptions")
    image: Image | None = None
    fixture_phash: str | None = Field(default=None, alias="fixturePhash")


class SearchResponse(EbayModel):
    href: str | None = None
    total: int | None = None
    limit: int | None = None
    offset: int | None = None
    next: str | None = None
    item_summaries: list[ItemSummary] = Field(default_factory=list, alias="itemSummaries")


class Item(ItemSummary):
    pass


@dataclass(frozen=True)
class ListingCandidate:
    marketplace_item_id: str
    title: str
    price: Decimal
    currency: str
    shipping_price: Decimal | None
    shipping_currency: str | None
    shipping_included: bool | None
    seller_id: str | None
    item_url: str | None
    image_url: str | None
    condition_raw: str | None
    raw_payload: dict[str, Any]


def to_candidate(summary: ItemSummary) -> ListingCandidate:
    shipping_price: Decimal | None = None
    shipping_currency: str | None = None
    shipping_included: bool | None = None

    for option in summary.shipping_options:
        if option.shipping_cost is None:
            continue
        shipping_price = option.shipping_cost.value
        shipping_currency = option.shipping_cost.currency
        shipping_included = shipping_price == Decimal("0")
        break

    return ListingCandidate(
        marketplace_item_id=summary.item_id,
        title=summary.title,
        price=summary.price.value,
        currency=summary.price.currency,
        shipping_price=shipping_price,
        shipping_currency=shipping_currency,
        shipping_included=shipping_included,
        seller_id=summary.seller.username if summary.seller else None,
        item_url=summary.item_web_url,
        image_url=summary.image.image_url if summary.image else None,
        condition_raw=summary.condition,
        raw_payload=summary.model_dump(mode="json", by_alias=True, exclude_none=True),
    )
