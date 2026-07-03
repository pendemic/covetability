from __future__ import annotations

import json
import re
from pathlib import Path

from app.contract import GoldLabelVerdict, MatchStatus
from app.matching.matcher import CatalogIndex, match_listing

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "ebay"


def fixture_titles() -> dict[str, str]:
    items: dict[str, str] = {}
    for path in (FIXTURES_DIR / "search").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload["itemSummaries"]:
            items[item["itemId"]] = item["title"]
    return items


def expected_labels() -> list[dict]:
    return json.loads((FIXTURES_DIR / "expected_labels.json").read_text(encoding="utf-8"))


def test_fixture_expected_labels_cover_every_unique_fixture_item() -> None:
    labels = expected_labels()

    assert {label["item_id"] for label in labels} == set(fixture_titles())


def test_readme_trap_inventory_matches_expected_labels_json() -> None:
    readme = (FIXTURES_DIR / "README.md").read_text(encoding="utf-8")
    labels_by_id = {label["item_id"]: label for label in expected_labels()}

    rows = [
        match.groups()
        for line in readme.splitlines()
        if (
            match := re.match(
                r"^\| [^|]+ \| `(v1\|fx-[^`]+)` \| [^|]+ \| `([^`]+)` \|$",
                line,
            )
        )
    ]
    assert rows
    for item_id, expected in rows:
        label = labels_by_id[item_id]
        if expected == "accepted_separate_market":
            assert label["verdict"] == GoldLabelVerdict.accept.value
            assert label["variant"] == "Le City reissue"
        else:
            assert label["verdict"] == GoldLabelVerdict.reject.value
            assert label["rejection_reason"] == expected


def test_matcher_catches_all_fixture_rejects_and_accepts_fixture_accepts() -> None:
    index = CatalogIndex.from_seed()
    titles = fixture_titles()

    for label in expected_labels():
        result = match_listing(titles[label["item_id"]], index, candidate_bag_slug=label["bag_slug"])
        if label["verdict"] == GoldLabelVerdict.reject.value:
            assert not (
                result.status == MatchStatus.auto_accepted and result.bag_slug == label["bag_slug"]
            ), label["item_id"]
        else:
            assert result.status != MatchStatus.auto_rejected, label["item_id"]
            assert result.bag_slug == label["bag_slug"], label["item_id"]


def test_le_city_fixture_is_accepted_as_separate_market_variant() -> None:
    index = CatalogIndex.from_seed()
    title = fixture_titles()["v1|fx-balenciaga-city-007|0"]

    result = match_listing(title, index, candidate_bag_slug="balenciaga-city")

    assert result.status == MatchStatus.auto_accepted
    assert result.bag_slug == "balenciaga-city"
    assert result.variant_name == "Le City reissue"
    assert result.trace["selected"] == "balenciaga-city"


def test_exclusion_trace_keeps_rejection_reason() -> None:
    index = CatalogIndex.from_seed()

    result = match_listing(
        "Dior saddle inspired monogram style shoulder purse",
        index,
        candidate_bag_slug="dior-saddle",
    )

    assert result.status == MatchStatus.auto_rejected
    assert result.suggested_rejection_reason is not None
    selected = result.trace["candidates"][0]
    assert selected["exclusions"][0]["reason"] == "replica_or_inspired"
