from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contract import AliasType, ExclusionScope, RejectionReason, VariantKind
from app.db import SessionLocal
from app.models import BagAlias, BagModel, BagVariant, Brand, ExclusionTerm

TRACKING_START = date(2026, 7, 1)

GLOBAL_EXCLUSIONS = [
    ("replica", RejectionReason.replica_or_inspired),
    ("inspired", RejectionReason.replica_or_inspired),
    ("style of", RejectionReason.replica_or_inspired),
    ("dupe", RejectionReason.replica_or_inspired),
    ("look-alike", RejectionReason.replica_or_inspired),
    ("type bag", RejectionReason.replica_or_inspired),
    ("dust bag only", RejectionReason.accessory_replacement_part),
    ("box only", RejectionReason.accessory_replacement_part),
    ("authentication card only", RejectionReason.accessory_replacement_part),
    ("receipt only", RejectionReason.accessory_replacement_part),
    ("strap only", RejectionReason.accessory_replacement_part),
    ("charm", RejectionReason.accessory_replacement_part),
    ("keychain", RejectionReason.accessory_replacement_part),
    ("wallet", RejectionReason.wrong_product_category),
    ("coin purse", RejectionReason.wrong_product_category),
    ("mirror only", RejectionReason.accessory_replacement_part),
    ("lock only", RejectionReason.accessory_replacement_part),
    ("key only", RejectionReason.accessory_replacement_part),
    ("repair", RejectionReason.accessory_replacement_part),
    ("for parts", RejectionReason.accessory_replacement_part),
    ("wanted", RejectionReason.wanted_to_buy),
    ("WTB", RejectionReason.wanted_to_buy),
    ("ISO", RejectionReason.wanted_to_buy),
    ("custom", RejectionReason.wrong_product_category),
    ("handmade", RejectionReason.wrong_product_category),
    ("doll", RejectionReason.wrong_product_category),
    ("miniature", RejectionReason.wrong_product_category),
    ("toy", RejectionReason.wrong_product_category),
    ("sticker", RejectionReason.wrong_product_category),
    ("poster", RejectionReason.wrong_product_category),
    ("phone case", RejectionReason.wrong_product_category),
]

CATALOG = [
    {
        "brand": {"slug": "chloe", "name": "Chloé"},
        "slug": "chloe-paddington",
        "model_name": "Paddington",
        "era": "Phoebe Philo for Chloé, S/S 2005-~2008",
        "expected_range_note": (
            "Expected asking range: about $300 Fair incomplete to $1,800 Excellent full set; "
            "typical Good/Very Good about $550-$950."
        ),
        "editorial_condition_notes": (
            "Leather scratches and patina, padlock tarnish, and missing lock or key are first-order "
            "condition and completeness signals."
        ),
        "initial_queries": [
            "chloe paddington bag",
            "chloe paddington satchel",
            "chloe padlock bag",
        ],
        "aliases": [
            ("Paddington Lock Bag", AliasType.alias),
            ("Chloé Padlock Bag", AliasType.alias),
            ("Chloe Padlock Bag", AliasType.alias),
            ("Paddington Satchel", AliasType.alias),
            ("Chloe paddington", AliasType.alias),
            ("Chloe paddington bag", AliasType.marketplace_term),
            ("Chloe lock bag", AliasType.marketplace_term),
            ("Chloe padlock satchel", AliasType.marketplace_term),
        ],
        "variants": [
            ("Medium", VariantKind.size, "Canonical satchel size.", False),
            ("Mini", VariantKind.size, "Smaller Paddington listings need size confirmation.", False),
            ("Bowler", VariantKind.size, "Shape variant commonly listed under Paddington.", False),
            ("Tote", VariantKind.size, "Shape variant commonly listed under Paddington.", False),
            ("Zippy", VariantKind.size, "Shape variant; lower confidence from titles alone.", False),
            ("Capsule editions", VariantKind.edition, "Coarse edition bucket for limited capsules.", False),
        ],
        "exclusions": [
            ("Paddington Bear", RejectionReason.wrong_product_category),
            ("Paddington 2", RejectionReason.wrong_product_category),
            ("teddy", RejectionReason.wrong_product_category),
            ("plush", RejectionReason.wrong_product_category),
            ("DVD", RejectionReason.wrong_product_category),
            ("marmalade", RejectionReason.wrong_product_category),
            ("Chloé Edith", RejectionReason.wrong_model),
            ("Chloe Edith", RejectionReason.wrong_model),
            ("Silverado", RejectionReason.wrong_model),
        ],
    },
    {
        "brand": {"slug": "balenciaga", "name": "Balenciaga"},
        "slug": "balenciaga-city",
        "model_name": "City",
        "era": "Nicolas Ghesquière motorcycle line, 2001-",
        "expected_range_note": (
            "Expected asking range: about $350 Fair to $1,600 Excellent; typical Good/Very Good "
            "about $500-$900."
        ),
        "editorial_condition_notes": (
            "Corner wear, handle darkening, missing mirror, and split or missing tassels are common "
            "condition drivers."
        ),
        "initial_queries": [
            "balenciaga city bag",
            "balenciaga classic city",
            "balenciaga motorcycle bag city",
        ],
        "aliases": [
            ("Classic City", AliasType.alias),
            ("Moto City", AliasType.alias),
            ("Motorcycle Bag", AliasType.marketplace_term),
            ("City Bag", AliasType.alias),
            ("Balenciaga City", AliasType.alias),
            ("Balenciaga Classic City", AliasType.alias),
            ("G12 City", AliasType.marketplace_term),
            ("G21 City", AliasType.marketplace_term),
            ("Metallic Edge City", AliasType.marketplace_term),
            ("Graffiti City", AliasType.marketplace_term),
            ("Le City", AliasType.marketplace_term),
        ],
        "variants": [
            ("City", VariantKind.size, "Canonical City size.", False),
            ("Small City", VariantKind.size, "Size split requires measurement confirmation.", False),
            ("Mini City", VariantKind.size, "Size split requires measurement confirmation.", False),
            ("Le City reissue", VariantKind.edition, "2024 reissue is a distinct market.", True),
        ],
        "exclusions": [
            ("First", RejectionReason.child_mini_variant_mismatched),
            ("Twiggy", RejectionReason.wrong_model),
            ("Town", RejectionReason.wrong_model),
            ("Work", RejectionReason.wrong_model),
            ("Weekender", RejectionReason.wrong_model),
            ("Part Time", RejectionReason.wrong_model),
            ("Part-Time", RejectionReason.wrong_model),
            ("Velo", RejectionReason.wrong_model),
            ("Day", RejectionReason.wrong_model),
            ("Hip", RejectionReason.wrong_model),
            ("Neo Classic", RejectionReason.wrong_model),
        ],
    },
    {
        "brand": {"slug": "fendi", "name": "Fendi"},
        "slug": "fendi-baguette",
        "model_name": "Baguette",
        "era": "Silvia Venturini Fendi, 1997-; 2019 relaunch ongoing",
        "expected_range_note": (
            "Expected asking range: about $300 Fair vintage to $2,500+ Excellent embellished; "
            "typical vintage Zucca Good/Very Good about $500-$1,100."
        ),
        "editorial_condition_notes": (
            "Zucca canvas edge wear, sticky vintage lining, and bead or sequin loss are key "
            "condition signals."
        ),
        "initial_queries": [
            "fendi baguette bag",
            "fendi zucca baguette",
            "fendi baguette vintage",
        ],
        "aliases": [
            ("Zucca Baguette", AliasType.alias),
            ("FF Baguette", AliasType.alias),
            ("Mamma Baguette", AliasType.marketplace_term),
            ("Mama Baguette", AliasType.marketplace_term),
            ("Sex and the City bag", AliasType.marketplace_term),
            ("1997 re-edition", AliasType.marketplace_term),
            ("Fendi baguette vintage", AliasType.marketplace_term),
            ("Fendi FF shoulder bag", AliasType.marketplace_term),
            ("Fendi zucca shoulder", AliasType.marketplace_term),
        ],
        "variants": [
            ("Baguette", VariantKind.size, "Canonical about 26cm model.", False),
            ("Mini/Micro Baguette", VariantKind.size, "Small sizes require title and measurement checks.", False),
            ("Zucca canvas", VariantKind.color_family, "Coarse material/color-family bucket.", False),
            ("Leather", VariantKind.color_family, "Coarse material/color-family bucket.", False),
            ("Embellished", VariantKind.edition, "Beaded, sequin, and seasonal embellished pieces.", False),
            ("Baguette 1997 re-edition", VariantKind.edition, "Re-edition market split.", True),
        ],
        "exclusions": [
            ("Mama Forever", RejectionReason.wrong_model),
            ("Mamma Forever", RejectionReason.wrong_model),
            ("Mamma", RejectionReason.seller_misuses_model_name),
            ("croissant", RejectionReason.wrong_model),
            ("Peekaboo", RejectionReason.wrong_model),
            ("Spy", RejectionReason.wrong_model),
            ("baguette charm", RejectionReason.accessory_replacement_part),
            ("bread", RejectionReason.wrong_product_category),
            ("bakery", RejectionReason.wrong_product_category),
        ],
    },
    {
        "brand": {"slug": "dior", "name": "Dior"},
        "slug": "dior-saddle",
        "model_name": "Saddle",
        "era": "John Galliano S/S 2000; Maria Grazia Chiuri reissue 2018-",
        "expected_range_note": (
            "Expected asking range: vintage about $500 Fair to $2,500 Excellent rare print; "
            "modern about $2,000-$4,500."
        ),
        "editorial_condition_notes": (
            "Canvas corner wear, Dior-logo lining wear, and hardware plating loss are common "
            "vintage condition issues."
        ),
        "initial_queries": [
            "dior saddle bag",
            "dior saddle oblique",
            "christian dior saddle vintage",
        ],
        "aliases": [
            ("Saddle Bag", AliasType.alias),
            ("Dior Oblique Saddle", AliasType.alias),
            ("Galliano Saddle", AliasType.alias),
            ("Trotter Saddle", AliasType.marketplace_term),
            ("Christian Dior Saddle", AliasType.alias),
            ("Dior Trotter bag", AliasType.marketplace_term),
            ("Dior Saddle vintage", AliasType.marketplace_term),
            ("Dior Rasta Saddle", AliasType.marketplace_term),
        ],
        "variants": [
            ("Vintage Galliano Saddle", VariantKind.edition, "2000s market split.", True),
            ("Modern Saddle", VariantKind.edition, "2018+ market split.", True),
            ("Mini Saddle", VariantKind.size, "Mini size needs measurement confirmation.", False),
            ("Saddle with strap", VariantKind.edition, "2018+ strap configuration.", False),
            ("Seasonal prints", VariantKind.edition, "Rasta, Girly, Denim, embroidered, and similar prints.", False),
        ],
        "exclusions": [
            ("horse saddle", RejectionReason.wrong_product_category),
            ("equestrian", RejectionReason.wrong_product_category),
            ("saddle pad", RejectionReason.wrong_product_category),
            ("western", RejectionReason.wrong_product_category),
            ("saddle style", RejectionReason.replica_or_inspired),
            ("Gucci saddle", RejectionReason.wrong_model),
            ("belt", RejectionReason.wrong_product_category),
            ("card holder", RejectionReason.wrong_product_category),
        ],
    },
    {
        "brand": {"slug": "louis-vuitton", "name": "Louis Vuitton"},
        "slug": "louis-vuitton-pochette-accessoires",
        "model_name": "Pochette Accessoires",
        "era": "1992-; Monogram canvas canonical",
        "expected_range_note": (
            "Expected asking range: about $200 Fair to $900 Excellent Monogram; typical Good/Very "
            "Good about $300-$550, with Multicolore commanding a premium."
        ),
        "editorial_condition_notes": (
            "Vachetta patina, sticky 1990s lining, and date-code legibility drive condition reads."
        ),
        "initial_queries": [
            "louis vuitton pochette accessoires",
            "louis vuitton pochette monogram",
            "lv pochette accessories",
        ],
        "aliases": [
            ("Pochette", AliasType.alias),
            ("LV Pochette", AliasType.alias),
            ("Pochette Accessories", AliasType.misspelling),
            ("Pochette Accessoires", AliasType.alias),
            ("Louis Vuitton Pochette", AliasType.alias),
            ("LV Pochette Accessories", AliasType.misspelling),
            ("LV Accessoires", AliasType.marketplace_term),
            ("Pochette NM", AliasType.marketplace_term),
            ("Pochette Monogram", AliasType.marketplace_term),
            ("LV pochette monogram", AliasType.marketplace_term),
        ],
        "variants": [
            ("Pochette Accessoires", VariantKind.size, "Canonical about 21cm model.", False),
            ("Pochette Accessoires NM", VariantKind.edition, "2020+ larger re-edition market.", True),
            ("Monogram", VariantKind.color_family, "Canonical brown monogram canvas.", False),
            ("Damier Ebene", VariantKind.color_family, "Canvas color-family bucket.", False),
            ("Damier Azur", VariantKind.color_family, "Canvas color-family bucket.", False),
            ("Multicolore", VariantKind.color_family, "Murakami Multicolore market bucket.", False),
            ("Vernis", VariantKind.color_family, "Vernis material/color-family bucket.", False),
        ],
        "exclusions": [
            ("Mini Pochette", RejectionReason.child_mini_variant_mismatched),
            ("Pochette Métis", RejectionReason.wrong_model),
            ("Pochette Metis", RejectionReason.wrong_model),
            ("Pochette Félicie", RejectionReason.wrong_model),
            ("Pochette Felicie", RejectionReason.wrong_model),
            ("Toiletry Pouch", RejectionReason.wrong_model),
            ("wristlet strap only", RejectionReason.accessory_replacement_part),
            ("extender chain only", RejectionReason.accessory_replacement_part),
            ("insert", RejectionReason.accessory_replacement_part),
            ("organizer", RejectionReason.accessory_replacement_part),
            ("Kirigami", RejectionReason.wrong_model),
            ("wapity", RejectionReason.wrong_model),
        ],
    },
]


def upsert_brand(session: Session, brand_data: dict[str, str]) -> Brand:
    brand = session.scalar(select(Brand).where(Brand.slug == brand_data["slug"]))
    if brand is None:
        brand = Brand(slug=brand_data["slug"], name=brand_data["name"])
        session.add(brand)
        session.flush()
    else:
        brand.name = brand_data["name"]
    return brand


def upsert_bag(session: Session, item: dict) -> BagModel:
    brand = upsert_brand(session, item["brand"])
    bag = session.scalar(select(BagModel).where(BagModel.slug == item["slug"]))
    if bag is None:
        bag = BagModel(slug=item["slug"], brand=brand, model_name=item["model_name"])
        session.add(bag)
        session.flush()

    bag.brand = brand
    bag.model_name = item["model_name"]
    bag.era = item["era"]
    bag.editorial_condition_notes = item["editorial_condition_notes"]
    bag.expected_range_note = item["expected_range_note"]
    bag.initial_queries = item["initial_queries"]
    bag.tracking_since = TRACKING_START
    return bag


def upsert_alias(session: Session, bag: BagModel, alias: str, alias_type: AliasType) -> None:
    row = session.scalar(
        select(BagAlias).where(BagAlias.bag_model_id == bag.id, BagAlias.alias == alias)
    )
    if row is None:
        session.add(BagAlias(bag_model=bag, alias=alias, type=alias_type))
    else:
        row.type = alias_type


def upsert_variant(
    session: Session,
    bag: BagModel,
    name: str,
    kind: VariantKind,
    attribution_confidence: str,
    is_separate_market: bool,
) -> None:
    row = session.scalar(
        select(BagVariant).where(BagVariant.bag_model_id == bag.id, BagVariant.name == name)
    )
    if row is None:
        session.add(
            BagVariant(
                bag_model=bag,
                name=name,
                kind=kind,
                attribution_confidence=attribution_confidence,
                is_separate_market=is_separate_market,
            )
        )
    else:
        row.kind = kind
        row.attribution_confidence = attribution_confidence
        row.is_separate_market = is_separate_market


def upsert_exclusion(
    session: Session,
    term: str,
    reason: RejectionReason,
    bag: BagModel | None = None,
) -> None:
    scope = ExclusionScope.bag if bag is not None else ExclusionScope.global_scope
    query = select(ExclusionTerm).where(ExclusionTerm.scope == scope, ExclusionTerm.term == term)
    query = query.where(ExclusionTerm.bag_model_id == bag.id) if bag is not None else query.where(
        ExclusionTerm.bag_model_id.is_(None)
    )
    row = session.scalar(query)
    if row is None:
        session.add(ExclusionTerm(bag_model=bag, term=term, scope=scope, reason=reason))
    else:
        row.reason = reason


def seed(session: Session) -> None:
    for term, reason in GLOBAL_EXCLUSIONS:
        upsert_exclusion(session, term=term, reason=reason)

    for item in CATALOG:
        bag = upsert_bag(session, item)
        for alias, alias_type in item["aliases"]:
            upsert_alias(session, bag, alias, alias_type)
        for name, kind, attribution_confidence, is_separate_market in item["variants"]:
            upsert_variant(session, bag, name, kind, attribution_confidence, is_separate_market)
        for term, reason in item["exclusions"]:
            upsert_exclusion(session, term=term, reason=reason, bag=bag)


def main() -> None:
    with SessionLocal() as session:
        seed(session)
        session.commit()

        bag_count = session.scalar(select(func.count()).select_from(BagModel))
        alias_count = session.scalar(select(func.count()).select_from(BagAlias))
        exclusion_count = session.scalar(select(func.count()).select_from(ExclusionTerm))
        print(
            f"Seeded catalog: {bag_count} bags, {alias_count} aliases, "
            f"{exclusion_count} exclusion terms."
        )


if __name__ == "__main__":
    main()
