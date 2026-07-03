from app.matching.keywords import extract_color_family, extract_edition, extract_size
from app.matching.normalize import contains_term, extract_measurements, normalize_title


def test_normalize_title_deaccents_and_strips_punctuation() -> None:
    normalized = normalize_title("Chloé Paddington Part-Time 9\" bag")

    assert normalized.text == "chloe paddington part time 9 bag"
    assert normalized.tokens == ("chloe", "paddington", "part", "time", "9", "bag")
    assert contains_term(normalized.text, "Part-Time")
    assert not contains_term(normalized.text, "padding")


def test_extract_measurements_preserves_inches_before_punctuation_strip() -> None:
    measurements = extract_measurements('Balenciaga Mini City measurements 9" x 6"')

    assert [(item.value, item.unit) for item in measurements] == [(9, "in"), (6, "in")]


def test_keyword_extractors_find_fixture_variants_and_colors() -> None:
    lv = normalize_title("Louis Vuitton Pochette Accessoires NM monogram larger re-edition")
    fendi = normalize_title("Fendi 1997 re-edition Baguette brown FF canvas")
    balenciaga = normalize_title('Balenciaga Mini City black bag measurements 9 inch')

    assert extract_edition("louis-vuitton-pochette-accessoires", lv) == "Pochette Accessoires NM"
    assert extract_color_family("louis-vuitton-pochette-accessoires", lv) == "Monogram"
    assert extract_edition("fendi-baguette", fendi) == "Baguette 1997 re-edition"
    assert extract_size("balenciaga-city", balenciaga) == "Mini City"
