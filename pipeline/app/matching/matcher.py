from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.contract import MATCH_AUTO_ACCEPT, MATCH_REVIEW_FLOOR, MatchStatus, RejectionReason
from app.matching.keywords import brand_hits, confirming_hits, extract_variant_name
from app.matching.normalize import NormalizedTitle, contains_term, normalize_text, normalize_title
from app.models import BagModel, ExclusionTerm
from seeds.catalog import CATALOG, GLOBAL_EXCLUSIONS

MATCHER_VERSION = "1.0"

BRAND_WEIGHT = 0.30
ALIAS_WEIGHT = 0.45
CONFIRMING_SIGNAL_WEIGHT = 0.10
CONFIRMING_SIGNAL_CAP = 0.20
VARIANT_WEIGHT = 0.05
EXCLUSION_WEIGHT = -0.60


@dataclass(frozen=True)
class CatalogVariant:
    id: int | None
    name: str
    is_separate_market: bool


@dataclass(frozen=True)
class CatalogExclusion:
    term: str
    reason: RejectionReason
    scope: str


@dataclass(frozen=True)
class CatalogBag:
    id: int | None
    slug: str
    brand_name: str
    model_name: str
    aliases: tuple[str, ...]
    variants: tuple[CatalogVariant, ...]
    exclusions: tuple[CatalogExclusion, ...]

    @property
    def variant_names(self) -> set[str]:
        return {variant.name for variant in self.variants}


@dataclass(frozen=True)
class CatalogIndex:
    bags: dict[str, CatalogBag]
    global_exclusions: tuple[CatalogExclusion, ...]

    @classmethod
    def from_session(cls, session: Session) -> CatalogIndex:
        bags = session.scalars(
            select(BagModel)
            .options(
                selectinload(BagModel.brand),
                selectinload(BagModel.aliases),
                selectinload(BagModel.variants),
                selectinload(BagModel.exclusion_terms),
            )
            .order_by(BagModel.slug)
        ).all()
        global_rows = session.scalars(
            select(ExclusionTerm).where(ExclusionTerm.bag_model_id.is_(None)).order_by(ExclusionTerm.term)
        ).all()
        return cls(
            bags={
                bag.slug: CatalogBag(
                    id=bag.id,
                    slug=bag.slug,
                    brand_name=bag.brand.name,
                    model_name=bag.model_name,
                    aliases=tuple(alias.alias for alias in sorted(bag.aliases, key=lambda row: row.alias)),
                    variants=tuple(
                        CatalogVariant(
                            id=variant.id,
                            name=variant.name,
                            is_separate_market=variant.is_separate_market,
                        )
                        for variant in sorted(bag.variants, key=lambda row: row.name)
                    ),
                    exclusions=tuple(
                        CatalogExclusion(term=row.term, reason=row.reason, scope="bag")
                        for row in sorted(bag.exclusion_terms, key=lambda item: item.term)
                    ),
                )
                for bag in bags
            },
            global_exclusions=tuple(
                CatalogExclusion(term=row.term, reason=row.reason, scope="global") for row in global_rows
            ),
        )

    @classmethod
    def from_seed(cls) -> CatalogIndex:
        bags: dict[str, CatalogBag] = {}
        for idx, item in enumerate(CATALOG, start=1):
            bags[item["slug"]] = CatalogBag(
                id=idx,
                slug=item["slug"],
                brand_name=item["brand"]["name"],
                model_name=item["model_name"],
                aliases=tuple(alias for alias, _alias_type in sorted(item["aliases"])),
                variants=tuple(
                    CatalogVariant(id=variant_idx, name=name, is_separate_market=is_separate_market)
                    for variant_idx, (name, _kind, _note, is_separate_market) in enumerate(
                        sorted(item["variants"]),
                        start=1,
                    )
                ),
                exclusions=tuple(
                    CatalogExclusion(term=term, reason=reason, scope="bag")
                    for term, reason in sorted(item["exclusions"])
                ),
            )
        return cls(
            bags=bags,
            global_exclusions=tuple(
                CatalogExclusion(term=term, reason=reason, scope="global")
                for term, reason in sorted(GLOBAL_EXCLUSIONS)
            ),
        )

    def bag_id_for_slug(self, slug: str | None) -> int | None:
        if slug is None or slug not in self.bags:
            return None
        return self.bags[slug].id

    def variant_id_for_name(self, bag_slug: str | None, variant_name: str | None) -> int | None:
        if bag_slug is None or variant_name is None:
            return None
        bag = self.bags.get(bag_slug)
        if bag is None:
            return None
        for variant in bag.variants:
            if variant.name == variant_name:
                return variant.id
        return None


@dataclass(frozen=True)
class MatchResult:
    bag_slug: str | None
    variant_name: str | None
    confidence: float
    status: MatchStatus
    trace: dict[str, Any]
    suggested_rejection_reason: RejectionReason | None = None


def match_listing(
    title: str,
    index: CatalogIndex,
    *,
    candidate_bag_slug: str | None = None,
) -> MatchResult:
    normalized = normalize_title(title)
    candidate_slugs = candidate_candidates(normalized, index, candidate_bag_slug)
    scored = [score_candidate(index.bags[slug], index.global_exclusions, normalized) for slug in candidate_slugs]

    if not scored:
        trace = base_trace(normalized, [])
        trace["selected"] = None
        trace["status"] = MatchStatus.auto_rejected.value
        return MatchResult(
            bag_slug=None,
            variant_name=None,
            confidence=0.0,
            status=MatchStatus.auto_rejected,
            trace=trace,
        )

    scored.sort(
        key=lambda item: (
            item["confidence"],
            item["bag_slug"] == candidate_bag_slug,
            -candidate_slugs.index(item["bag_slug"]),
        ),
        reverse=True,
    )
    selected = scored[0]
    status = status_for_confidence(selected["confidence"])
    suggested_reason = selected.get("suggested_rejection_reason")
    if status == MatchStatus.auto_rejected:
        bag_slug = None
        variant_name = None
    else:
        bag_slug = selected["bag_slug"]
        variant_name = selected.get("variant")

    trace = base_trace(normalized, scored)
    trace["selected"] = selected["bag_slug"]
    trace["status"] = status.value
    trace["suggested_rejection_reason"] = suggested_reason
    trace["candidate_bag_slug"] = candidate_bag_slug

    return MatchResult(
        bag_slug=bag_slug,
        variant_name=variant_name,
        confidence=selected["confidence"],
        status=status,
        trace=trace,
        suggested_rejection_reason=RejectionReason(suggested_reason) if suggested_reason else None,
    )


def candidate_candidates(
    normalized: NormalizedTitle,
    index: CatalogIndex,
    candidate_bag_slug: str | None,
) -> list[str]:
    slugs: list[str] = []
    for slug, bag in index.bags.items():
        if brand_hits(slug, normalized) or alias_terms(bag, normalized):
            slugs.append(slug)
    if candidate_bag_slug in index.bags and candidate_bag_slug not in slugs:
        slugs.append(candidate_bag_slug)
    return slugs


def score_candidate(
    bag: CatalogBag,
    global_exclusions: tuple[CatalogExclusion, ...],
    normalized: NormalizedTitle,
) -> dict[str, Any]:
    confidence = 0.0
    hits: list[dict[str, Any]] = []

    detected_brand = brand_hits(bag.slug, normalized)
    if detected_brand:
        confidence += BRAND_WEIGHT
        hits.append(hit("brand", detected_brand[0], BRAND_WEIGHT))

    aliases = alias_terms(bag, normalized)
    if aliases:
        confidence += ALIAS_WEIGHT
        hits.append(hit("alias", aliases[0], ALIAS_WEIGHT))

    confirming = confirming_hits(bag.slug, normalized)
    for term in confirming[: int(CONFIRMING_SIGNAL_CAP / CONFIRMING_SIGNAL_WEIGHT)]:
        confidence += CONFIRMING_SIGNAL_WEIGHT
        hits.append(hit("confirming_signal", term, CONFIRMING_SIGNAL_WEIGHT))

    variant = extract_variant_name(bag.slug, normalized, bag.variant_names)
    if variant is not None:
        confidence += VARIANT_WEIGHT
        hits.append(hit("variant", variant, VARIANT_WEIGHT))

    exclusions = exclusion_hits(bag, global_exclusions, normalized)
    for _exclusion in exclusions:
        confidence += EXCLUSION_WEIGHT

    confidence = max(0.0, min(1.0, round(confidence, 4)))
    suggested_reason = exclusions[0]["reason"] if exclusions else None
    return {
        "bag_slug": bag.slug,
        "confidence": confidence,
        "hits": hits,
        "exclusions": exclusions,
        "variant": variant,
        "suggested_rejection_reason": suggested_reason,
    }


def alias_terms(bag: CatalogBag, normalized: NormalizedTitle) -> tuple[str, ...]:
    terms = [bag.model_name, *bag.aliases]
    return tuple(term for term in terms if contains_term(normalized.text, term))


def exclusion_hits(
    bag: CatalogBag,
    global_exclusions: tuple[CatalogExclusion, ...],
    normalized: NormalizedTitle,
) -> list[dict[str, Any]]:
    hits_by_term: dict[str, dict[str, Any]] = {}
    for exclusion in (*global_exclusions, *bag.exclusions):
        normalized_term = normalize_text(exclusion.term)
        if normalized_term in hits_by_term:
            continue
        if exclusion_is_suppressed(bag.slug, normalized_term, normalized):
            continue
        if contains_term(normalized.text, exclusion.term):
            hits_by_term[normalized_term] = {
                "term": exclusion.term,
                "scope": exclusion.scope,
                "reason": exclusion.reason.value,
                "weight": EXCLUSION_WEIGHT,
            }
    return list(hits_by_term.values())


def exclusion_is_suppressed(
    bag_slug: str,
    normalized_term: str,
    normalized: NormalizedTitle,
) -> bool:
    return (
        bag_slug == "dior-saddle"
        and normalized_term == "charm"
        and contains_term(normalized.text, "d charm")
    )


def hit(rule: str, term: str, weight: float) -> dict[str, Any]:
    return {"rule": rule, "term": term, "weight": weight}


def status_for_confidence(confidence: float) -> MatchStatus:
    if confidence >= MATCH_AUTO_ACCEPT:
        return MatchStatus.auto_accepted
    if confidence >= MATCH_REVIEW_FLOOR:
        return MatchStatus.needs_review
    return MatchStatus.auto_rejected


def base_trace(normalized: NormalizedTitle, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "matcher_version": MATCHER_VERSION,
        "normalized_title": normalized.text,
        "candidates": candidates,
    }
