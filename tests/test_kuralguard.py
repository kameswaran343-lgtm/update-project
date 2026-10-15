from __future__ import annotations

import copy
import json
import unicodedata
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.matcher import Matcher
from engine.normalize import normalize
from guard.api import ABSTAIN_MESSAGE, app
from guard.extractor import extract_candidates
from scripts.build_corpus import CorpusBuildError, _validate

ROOT = Path(__file__).resolve().parents[1]
with (ROOT / "data" / "clean" / "kural.json").open(encoding="utf-8") as source:
    CORPUS = json.load(source)

client = TestClient(app)


@pytest.fixture()
def matcher() -> Matcher:
    return Matcher(records=CORPUS)


def _one_letter_deleted(text: str) -> str:
    for index, character in enumerate(text):
        if (
            0x0B80 <= ord(character) <= 0x0BFF
            and unicodedata.category(character).startswith("L")
        ):
            return text[:index] + text[index + 1 :]
    raise AssertionError("Corpus sample has no Tamil letters.")


def test_normalization_keeps_only_normalized_tamil_words(matcher: Matcher) -> None:
    record = CORPUS[0]
    source = record["line1"] + " " + record["line2"]
    decorated = unicodedata.normalize("NFD", source) + "\u200b, 123 !!!"
    assert normalize(decorated) == normalize(source)


def test_exact_full_couplet_is_verified(matcher: Matcher) -> None:
    record = CORPUS[0]
    result = matcher.verify(f"{record['line1']}\n{record['line2']}")
    assert result.verdict == "verified"
    assert result.matched_id == record["id"]
    assert result.matched_scope == "full"


def test_flattened_full_couplet_is_not_verified(matcher: Matcher) -> None:
    record = CORPUS[0]
    result = matcher.verify(f"{record['line1']} {record['line2']}")
    assert result.verdict == "near_match"
    assert result.score < 100
    assert result.warning == "line_word_count_mismatch"


def test_full_couplet_with_wrong_line_word_counts_is_not_verified(
    matcher: Matcher,
) -> None:
    record = CORPUS[0]
    first_line_words = record["line1"].split()
    malformed = (
        f"{' '.join(first_line_words[:3])}\n"
        f"{' '.join(first_line_words[3:])} {record['line2']}"
    )
    result = matcher.verify(malformed)
    assert result.verdict == "near_match"
    assert result.score < 100
    assert result.warning == "line_word_count_mismatch"


def test_exact_corpus_shape_exception_is_not_verified(matcher: Matcher) -> None:
    record = next(
        item for item in CORPUS
        if len(normalize(item["line1"]).split()) != 4
        or len(normalize(item["line2"]).split()) != 3
    )
    result = matcher.verify(f"{record['line1']}\n{record['line2']}")
    assert result.verdict == "near_match"
    assert result.score < 100
    assert result.warning == "line_word_count_mismatch"


def test_punctuation_and_extra_spaces_are_ignored(matcher: Matcher) -> None:
    record = CORPUS[1]
    result = matcher.verify(f"  {record['line1']} !!!   \n  {record['line2']} ,  ")
    assert result.verdict == "verified"
    assert result.matched_id == record["id"]


def test_one_character_typo_is_a_near_match_with_diff(matcher: Matcher) -> None:
    record = CORPUS[2]
    text = f"{record['line1']} {record['line2']}"
    result = matcher.verify(_one_letter_deleted(text))
    assert result.verdict == "near_match"
    assert result.matched_id == record["id"]
    assert result.diff
    assert any(part.kind != "same" for part in result.diff)


def test_spliced_couplet_is_never_verified(matcher: Matcher) -> None:
    first, second = CORPUS[0], CORPUS[17]
    result = matcher.verify(f"{first['line1']} {second['line2']}")
    assert result.verdict in {"near_match", "not_found"}
    assert result.verdict != "verified"


@pytest.mark.parametrize("field", ["line1", "line2"])
def test_half_couplet_matches(field: str, matcher: Matcher) -> None:
    record = CORPUS[3]
    result = matcher.verify(record[field])
    assert result.verdict == "near_match"
    assert result.score < 100
    assert result.matched_id == record["id"]
    assert result.matched_scope == field
    assert result.warning == "line_word_count_mismatch"


def test_wrong_claimed_id_is_flagged_as_attribution_mismatch(
    matcher: Matcher,
) -> None:
    record = CORPUS[0]
    wrong_id = record["id"] + 1
    result = matcher.verify(f"{record['line1']}\n{record['line2']}", claimed_id=wrong_id)
    assert result.verdict == "verified"
    assert result.matched_id == record["id"]
    assert result.claimed_id_ok is False
    assert result.warning == "attribution_mismatch"


def test_matching_claimed_id_is_confirmed(matcher: Matcher) -> None:
    record = CORPUS[0]
    result = matcher.verify(f"{record['line1']}\n{record['line2']}", claimed_id=record["id"])
    assert result.claimed_id_ok is True
    assert result.warning is None


def test_corpus_validation_rejects_empty_line() -> None:
    invalid = copy.deepcopy(CORPUS)
    invalid[0]["line1"] = ""
    with pytest.raises(CorpusBuildError, match="empty line"):
        _validate(invalid)


def test_guard_extracts_quotes_and_associates_citation() -> None:
    record = CORPUS[0]
    other_a, other_b = CORPUS[8], CORPUS[13]
    fake = f"{other_a['line1']} {other_b['line2']}"
    answer = (
        f"“{record['line1']}\n{record['line2']}” — Kural {record['id']}.\n\n"
        + "Context without a quotation. " * 8
        + f"\n“{fake}”"
    )
    candidates = extract_candidates(answer)
    assert len(candidates) == 2
    assert candidates[0].claimed_id == record["id"]
    assert candidates[1].claimed_id is None


def test_guard_endpoint_annotates_one_real_and_one_spliced_quote() -> None:
    real, other = CORPUS[0], CORPUS[11]
    fake = f"{CORPUS[8]['line1']} {other['line2']}"
    response = client.post(
        "/api/guard",
        json={
            "llm_answer": (
                f"“{real['line1']}\n{real['line2']}” — Kural {real['id']}.\n\n"
                + "More context. " * 12
                + f"\n“{fake}”"
            )
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["quotes"]) == 2
    assert payload["summary"]["verified"] == 1
    assert payload["quotes"][0]["claimed_id_ok"] is True
    assert "✅ verified" in payload["annotated_answer"]
    assert "⚠️ near match" in payload["annotated_answer"] or "❌ not found" in payload["annotated_answer"]
    assert ABSTAIN_MESSAGE in payload["annotated_answer"] or payload["summary"]["near"] == 1


def test_verify_endpoint_uses_local_corpus() -> None:
    record = CORPUS[0]
    response = client.post(
        "/api/verify",
        json={"text": f"{record['line1']}\n{record['line2']}", "claimed_id": record["id"] + 1},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["verdict"] == "verified"
    assert payload["matched_id"] == record["id"]
    assert payload["warning"] == "attribution_mismatch"


def test_kural_lookup_and_health_endpoints() -> None:
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/healthz").json() == {"status": "ok"}
    assert client.get("/health").json() == {"status": "ok"}
    verses = client.get("/api/kurals/verses")
    assert verses.status_code == 200
    assert len(verses.json()) == 1330
    assert verses.json()[0] == {
        "id": CORPUS[0]["id"],
        "line1": CORPUS[0]["line1"],
        "line2": CORPUS[0]["line2"],
    }
    result = client.get(f"/api/kural/{CORPUS[0]['id']}")
    assert result.status_code == 200
    assert result.json()["id"] == CORPUS[0]["id"]
    assert client.get(f"/kural/{CORPUS[0]['id']}").status_code == 200
