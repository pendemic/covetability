from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.contract import ConditionBand, GoldLabelVerdict, RejectionReason


class LabelPayload(BaseModel):
    marketplace_item_id: str
    bag_model_id: int
    verdict: GoldLabelVerdict
    rejection_reason: RejectionReason | None = None
    accepted_variant_id: int | None = None
    color_family: str | None = None
    condition_band: ConditionBand | None = None
    strap_included: bool | None = None
    lock_included: bool | None = None
    key_included: bool | None = None
    dustbag_included: bool | None = None
    cards_included: bool | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def check_verdict_reason(self) -> LabelPayload:
        if self.verdict == GoldLabelVerdict.reject and self.rejection_reason is None:
            raise ValueError("reject labels require a rejection reason")
        if self.verdict == GoldLabelVerdict.accept and self.rejection_reason is not None:
            raise ValueError("accept labels cannot include a rejection reason")
        return self


class ReviewDecisionPayload(BaseModel):
    action: Literal["approve", "reassign", "reject"]
    bag_model_id: int | None = None
    variant_id: int | None = None
    rejection_reason: RejectionReason | None = None

    @model_validator(mode="after")
    def check_action_fields(self) -> ReviewDecisionPayload:
        if self.action == "reassign" and self.bag_model_id is None:
            raise ValueError("reassign requires bag_model_id")
        if self.action == "reject" and self.rejection_reason is None:
            raise ValueError("reject requires rejection_reason")
        return self


class PaginatedResponse(BaseModel):
    items: list[dict]
    total: int
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)
