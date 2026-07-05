from __future__ import annotations

import re

from seeds.catalog import CATALOG

PROHIBITED_PATTERNS = [
    re.compile(r"\bmarket value\b", re.IGNORECASE),
    re.compile(r"\bworth\b", re.IGNORECASE),
    re.compile(r"\bvaluation\b", re.IGNORECASE),
    re.compile(r"\bsold\b", re.IGNORECASE),
    re.compile(r"\bsell-through\b", re.IGNORECASE),
    re.compile(r"\bsales rate\b", re.IGNORECASE),
    re.compile(r"\bsales\b", re.IGNORECASE),
    re.compile(r"(?<!platform-)\bauthenticated\b", re.IGNORECASE),
    re.compile(r"\bdemand\b", re.IGNORECASE),
    re.compile(r"\binvestment\b", re.IGNORECASE),
    re.compile(r"\bappreciating\b", re.IGNORECASE),
    re.compile(r"\bROI\b", re.IGNORECASE),
    re.compile(r"\bforecast\b", re.IGNORECASE),
    re.compile(r"\bprediction\b", re.IGNORECASE),
]


def test_seeded_editorial_capsules_have_reviewable_length_and_clean_vocabulary() -> None:
    for item in CATALOG:
        history = item["editorial_history"]
        words = re.findall(r"\b[\w'-]+\b", history)
        assert 150 <= len(words) <= 300, item["slug"]

        editorial_text = " ".join(
            [
                item.get("editorial_summary") or "",
                history,
                item.get("editorial_condition_notes") or "",
            ]
        )
        assert not any(pattern.search(editorial_text) for pattern in PROHIBITED_PATTERNS), item["slug"]
