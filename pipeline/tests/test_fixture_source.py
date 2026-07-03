from pathlib import Path

from app.ingestion.fixtures import FixtureSource
from app.ingestion.source import slugify
from seeds.catalog import CATALOG

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "ebay"


def test_slugify_matches_fixture_filenames() -> None:
    assert slugify("Chloé Padlock Bag") == "chloe-padlock-bag"
    assert slugify("lv pochette accessories") == "lv-pochette-accessories"


def test_fixture_source_has_expected_per_bag_volume() -> None:
    source = FixtureSource(FIXTURES_DIR)

    for item in CATALOG:
        seen: set[str] = set()
        for query in item["initial_queries"]:
            summaries = list(source.search_active_listings(query))
            assert summaries, query
            seen.update(summary.item_id for summary in summaries)

        assert len(seen) >= 25, item["slug"]


def test_fixture_trap_ids_are_present() -> None:
    source = FixtureSource(FIXTURES_DIR)
    expected_ids = {
        "v1|fx-chloe-paddington-009|0",
        "v1|fx-balenciaga-city-008|0",
        "v1|fx-fendi-baguette-009|0",
        "v1|fx-dior-saddle-007|0",
        "v1|fx-lv-pochette-010|0",
    }

    seen: set[str] = set()
    for item in CATALOG:
        for query in item["initial_queries"]:
            seen.update(summary.item_id for summary in source.search_active_listings(query))

    assert expected_ids.issubset(seen)
