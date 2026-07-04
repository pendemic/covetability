from app.contract import ConditionBand

STRUCTURED_CONDITION_MAP: dict[str, ConditionBand] = {
    "new": ConditionBand.new_or_unused,
    "new with tags": ConditionBand.new_or_unused,
    "new without tags": ConditionBand.new_or_unused,
    "pre owned excellent": ConditionBand.excellent,
    "preowned excellent": ConditionBand.excellent,
    "excellent": ConditionBand.excellent,
    "pre owned very good": ConditionBand.very_good,
    "preowned very good": ConditionBand.very_good,
    "very good": ConditionBand.very_good,
    "pre owned good": ConditionBand.good,
    "preowned good": ConditionBand.good,
    "good": ConditionBand.good,
    "pre owned fair": ConditionBand.fair,
    "preowned fair": ConditionBand.fair,
    "fair": ConditionBand.fair,
    "pre owned poor": ConditionBand.poor,
    "preowned poor": ConditionBand.poor,
    "poor": ConditionBand.poor,
}

UNSTRUCTURED_CONDITIONS = {"pre owned", "preowned", "used"}

GLOBAL_DAMAGE_TERMS: tuple[tuple[str, ConditionBand], ...] = (
    ("sticky lining", ConditionBand.fair),
    ("cracked", ConditionBand.fair),
    ("as is", ConditionBand.fair),
    ("fair wear", ConditionBand.fair),
    ("worn edges", ConditionBand.good),
    ("worn corners", ConditionBand.good),
    ("tarnish", ConditionBand.good),
    ("tarnished", ConditionBand.good),
    ("bead loss", ConditionBand.good),
    ("plating wear", ConditionBand.good),
    ("missing", ConditionBand.good),
    ("no strap", ConditionBand.good),
)

GLOBAL_POSITIVE_TERMS: tuple[tuple[str, ConditionBand], ...] = (
    ("never used", ConditionBand.new_or_unused),
    ("new", ConditionBand.new_or_unused),
    ("pristine", ConditionBand.excellent),
    ("mint", ConditionBand.excellent),
    ("like new", ConditionBand.excellent),
    ("full set", ConditionBand.excellent),
    ("excellent", ConditionBand.excellent),
)

PER_BAG_CONDITION_TERMS: dict[str, tuple[tuple[str, ConditionBand], ...]] = {
    "chloe-paddington": (
        ("missing lock", ConditionBand.fair),
        ("missing key", ConditionBand.good),
        ("no key", ConditionBand.good),
        ("padlock tarnish", ConditionBand.good),
    ),
    "balenciaga-city": (
        ("mirror missing", ConditionBand.good),
        ("missing mirror", ConditionBand.good),
        ("split tassel", ConditionBand.good),
        ("split tassels", ConditionBand.good),
        ("missing tassels", ConditionBand.good),
        ("handle darkening", ConditionBand.good),
        ("darkened handles", ConditionBand.good),
    ),
    "fendi-baguette": (
        ("hologram missing", ConditionBand.good),
        ("sticky lining", ConditionBand.fair),
        ("bead loss", ConditionBand.good),
    ),
    "louis-vuitton-pochette-accessoires": (
        ("dark patina", ConditionBand.good),
        ("water spots", ConditionBand.good),
        ("sticky lining", ConditionBand.fair),
    ),
}
