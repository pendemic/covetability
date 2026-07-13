from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from app.matching.normalize import Measurement, NormalizedTitle, contains_term, extract_measurements

BRAND_TOKENS: dict[str, tuple[str, ...]] = {
    "chloe-paddington": ("chloe", "chloe"),
    "balenciaga-city": ("balenciaga",),
    "fendi-baguette": ("fendi",),
    "dior-saddle": ("dior", "christian dior"),
    "louis-vuitton-pochette-accessoires": ("louis vuitton", "lv"),
    # Extended catalog
    "chanel-25": ("chanel",),
    "chanel-suede-flap": ("chanel",),
    "dior-gaucho": ("dior", "christian dior"),
    "dior-columbus": ("dior", "christian dior"),
    "ysl-mombasa": ("ysl", "yves saint laurent", "saint laurent"),
    "miu-miu-vitello": ("miu miu",),
    "miu-miu-nappa": ("miu miu",),
    "miu-miu-pocket": ("miu miu",),
    "chloe-silverado": ("chloe",),
    "gucci-indy": ("gucci",),
    "gucci-jackie": ("gucci",),
    "prada-bonnie": ("prada",),
    "prada-bowling": ("prada",),
    "louis-vuitton-pochette": ("louis vuitton", "lv"),
    "fendi-spy": ("fendi",),
    "balenciaga-rodeo": ("balenciaga",),
}

CONFIRMING_SIGNALS: dict[str, tuple[str, ...]] = {
    "chloe-paddington": (
        "padlock",
        "lock",
        "key",
        "clochette",
        "satchel",
        "leather",
        "patina",
        "worn",
        "phoebe philo",
        "y2k",
    ),
    "balenciaga-city": (
        "motorcycle",
        "moto",
        "le city",
        "2024",
        "classic",
        "lambskin",
        "leather",
        "hardware",
        "mini city",
        "small city",
        "tassels",
        "tassel",
        "agneau",
        "chevre",
        "g12",
        "g21",
        "giant",
        "mirror",
    ),
    "fendi-baguette": (
        "ff",
        "zucca",
        "clasp",
        "buckle",
        "shoulder",
        "beaded",
        "sequin",
        "embroidered",
        "limited",
        "floral",
        "nappa",
        "canvas",
    ),
    "dior-saddle": (
        "oblique",
        "trotter",
        "galliano",
        "stirrup",
        "d charm",
        "leather",
        "calfskin",
        "hardware",
        "date code",
        "canvas",
        "logo",
        "rasta",
        "girly",
        "denim",
        "embroidered",
    ),
    "louis-vuitton-pochette-accessoires": (
        "monogram",
        "damier",
        "azur",
        "ebene",
        "multicolore",
        "murakami",
        "vernis",
        "vachetta",
        "date code",
        "canvas",
    ),
    # Extended catalog
    "chanel-25": ("flap", "cc", "chain", "quilted", "turnlock", "lambskin", "caviar", "leather"),
    "chanel-suede-flap": ("suede", "flap", "cc", "chain", "quilted", "classic", "turnlock", "vintage"),
    "dior-gaucho": ("gaucho", "saddle", "buckle", "double", "galliano", "distressed", "leather"),
    "dior-columbus": ("columbus", "avenue", "logo", "trotter", "canvas", "shoulder"),
    "ysl-mombasa": ("mombasa", "horn", "hobo", "tom ford", "crescent", "leather", "suede"),
    "miu-miu-vitello": ("vitello", "lux", "shine", "bow", "matelasse", "leather", "bugatti"),
    "miu-miu-nappa": ("nappa", "coffer", "bow", "gathered", "matelasse", "leather"),
    "miu-miu-pocket": ("pocket", "nappa", "hobo", "leather", "smooth", "strap"),
    "chloe-silverado": ("silverado", "ring", "wooden", "hobo", "leather", "phoebe philo"),
    "gucci-indy": ("indy", "hobo", "tassel", "fringe", "buckle", "canvas", "leather"),
    "gucci-jackie": ("jackie", "piston", "hobo", "canvas", "leather", "1961", "new jackie"),
    "prada-bonnie": ("bonnie", "bauletto", "saffiano", "leather", "bowling"),
    "prada-bowling": ("bowling", "bauletto", "tessuto", "nylon", "leather", "doctor"),
    "louis-vuitton-pochette": ("pochette", "monogram", "multicolore", "murakami", "vachetta", "canvas", "cles"),
    "fendi-spy": ("spy", "hobo", "leather", "secret", "compartment", "rope", "handle"),
    "balenciaga-rodeo": ("rodeo", "le rodeo", "hobo", "studded", "knot", "strap", "leather"),
}

SIZE_TERMS: dict[str, tuple[tuple[str, str], ...]] = {
    "chloe-paddington": (
        ("Mini", "mini"),
        ("Medium", "medium"),
        ("Bowler", "bowler"),
        ("Tote", "tote"),
        ("Zippy", "zippy"),
    ),
    "balenciaga-city": (
        ("Mini City", "mini city"),
        ("Small City", "small city"),
        ("City", "classic city"),
        ("City", "city"),
    ),
    "fendi-baguette": (
        ("Mini/Micro Baguette", "mini baguette"),
        ("Mini/Micro Baguette", "micro baguette"),
        ("Baguette", "baguette"),
    ),
    "dior-saddle": (
        ("Mini Saddle", "mini saddle"),
        ("Mini Saddle", "mini"),
    ),
    "louis-vuitton-pochette-accessoires": (
        ("Pochette Accessoires NM", "pochette nm"),
        ("Pochette Accessoires NM", "nm"),
        ("Pochette Accessoires", "pochette accessoires"),
        ("Pochette Accessoires", "pochette accessories"),
    ),
}

COLOR_FAMILIES: dict[str, tuple[tuple[str, str], ...]] = {
    "chloe-paddington": (
        ("black", "black"),
        ("brown", "brown"),
        ("brown", "chocolate"),
        ("brown", "whiskey"),
        ("tan", "tan"),
        ("cream", "cream"),
        ("cream", "ivory"),
        ("blue", "blue"),
        ("red", "red"),
        ("gray", "grey"),
        ("metallic", "metallic"),
    ),
    "balenciaga-city": (
        ("black", "black"),
        ("gray", "grey"),
        ("gray", "anthracite"),
        ("red", "red"),
        ("red", "rouge"),
        ("blue", "blue"),
        ("green", "green"),
        ("brown", "chocolate"),
        ("taupe", "taupe"),
        ("beige", "beige"),
    ),
    "fendi-baguette": (
        ("Zucca canvas", "zucca"),
        ("Zucca canvas", "ff canvas"),
        ("Leather", "leather"),
        ("Leather", "nappa"),
        ("black", "black"),
        ("brown", "brown"),
        ("cream", "cream"),
        ("tan", "tan"),
        ("purple", "purple"),
        ("multicolor", "multicolor"),
    ),
    "dior-saddle": (
        ("oblique", "oblique"),
        ("trotter", "trotter"),
        ("blue", "blue"),
        ("black", "black"),
        ("brown", "brown"),
        ("tan", "tan"),
        ("denim", "denim"),
        ("pink", "pink"),
        ("rasta", "rasta"),
    ),
    "louis-vuitton-pochette-accessoires": (
        ("Monogram", "monogram"),
        ("Damier Ebene", "damier ebene"),
        ("Damier Ebene", "ebene"),
        ("Damier Azur", "damier azur"),
        ("Damier Azur", "azur"),
        ("Multicolore", "multicolore"),
        ("Multicolore", "murakami"),
        ("Vernis", "vernis"),
    ),
}

EDITION_RULES: dict[str, tuple[tuple[str, str], ...]] = {
    "chloe-paddington": (
        ("Capsule editions", "capsule"),
        ("Capsule editions", "edition"),
    ),
    "balenciaga-city": (
        ("Le City reissue", "le city"),
        ("Le City reissue", "2024 reissue"),
        ("Small City", "small city"),
        ("Mini City", "mini city"),
    ),
    "fendi-baguette": (
        ("Baguette 1997 re-edition", "1997 re edition"),
        ("Baguette 1997 re-edition", "re edition"),
        ("Baguette 1997 re-edition", "2019 relaunch"),
        ("Embellished", "beaded"),
        ("Embellished", "sequin"),
        ("Embellished", "embroidered"),
        ("Embellished", "limited edition"),
        ("Embellished", "floral"),
    ),
    "dior-saddle": (
        ("Vintage Galliano Saddle", "vintage"),
        ("Vintage Galliano Saddle", "galliano"),
        ("Modern Saddle", "modern"),
        ("Modern Saddle", "2018"),
        ("Saddle with strap", "with strap"),
        ("Seasonal prints", "rasta"),
        ("Seasonal prints", "girly"),
        ("Seasonal prints", "denim"),
        ("Seasonal prints", "embroidered"),
    ),
    "louis-vuitton-pochette-accessoires": (
        ("Pochette Accessoires NM", "nm"),
        ("Pochette Accessoires NM", "larger re edition"),
        ("Pochette Accessoires NM", "2020"),
    ),
}


def matching_terms(normalized: NormalizedTitle, terms: Iterable[str]) -> tuple[str, ...]:
    return tuple(term for term in terms if contains_term(normalized.text, term))


def brand_hits(bag_slug: str, normalized: NormalizedTitle) -> tuple[str, ...]:
    return matching_terms(normalized, BRAND_TOKENS.get(bag_slug, ()))


def confirming_hits(bag_slug: str, normalized: NormalizedTitle) -> tuple[str, ...]:
    return matching_terms(normalized, CONFIRMING_SIGNALS.get(bag_slug, ()))


def extract_size(bag_slug: str, normalized: NormalizedTitle) -> str | None:
    measurement_size = size_from_measurements(bag_slug, extract_measurements(normalized.raw))
    if measurement_size is not None:
        return measurement_size
    return first_rule_match(normalized, SIZE_TERMS.get(bag_slug, ()))


def extract_color_family(bag_slug: str, normalized: NormalizedTitle) -> str | None:
    return first_rule_match(normalized, COLOR_FAMILIES.get(bag_slug, ()))


def extract_edition(bag_slug: str, normalized: NormalizedTitle) -> str | None:
    return first_rule_match(normalized, EDITION_RULES.get(bag_slug, ()))


def extract_variant_name(bag_slug: str, normalized: NormalizedTitle, variant_names: set[str]) -> str | None:
    edition = extract_edition(bag_slug, normalized)
    if edition in variant_names:
        return edition
    size = extract_size(bag_slug, normalized)
    if size in variant_names:
        return size
    color = extract_color_family(bag_slug, normalized)
    if color in variant_names:
        return color
    return None


def first_rule_match(normalized: NormalizedTitle, rules: Iterable[tuple[str, str]]) -> str | None:
    for value, term in rules:
        if contains_term(normalized.text, term):
            return value
    return None


def size_from_measurements(bag_slug: str, measurements: tuple[Measurement, ...]) -> str | None:
    if not measurements:
        return None
    largest_inches = max(to_inches(measurement) for measurement in measurements)
    if bag_slug == "balenciaga-city":
        if largest_inches <= Decimal("10"):
            return "Mini City"
        if largest_inches <= Decimal("13"):
            return "Small City"
        return "City"
    if bag_slug == "louis-vuitton-pochette-accessoires":
        if largest_inches >= Decimal("9.2"):
            return "Pochette Accessoires NM"
        return "Pochette Accessoires"
    return None


def to_inches(measurement: Measurement) -> Decimal:
    if measurement.unit == "cm":
        return measurement.value / Decimal("2.54")
    return measurement.value
