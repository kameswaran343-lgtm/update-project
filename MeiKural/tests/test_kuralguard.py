from __future__ import annotations

import copy
import json
import unicodedata
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from guard import education
from engine.corpora import CorpusUnavailableError, get_work_catalog, verify_literature
from engine.matcher import Matcher
from engine.normalize import normalize
from guard.api import ABSTAIN_MESSAGE, app
from guard.extractor import extract_candidates
from guard import memory
from scripts.build_corpus import CorpusBuildError, _validate

ROOT = Path(__file__).resolve().parents[1]
with (ROOT / "data" / "clean" / "kural.json").open(encoding="utf-8") as source:
    CORPUS = json.load(source)
with (ROOT / "data" / "clean" / "aathichudi.json").open(encoding="utf-8") as source:
    AATHICHUDI_CORPUS = json.load(source)
with (ROOT / "data" / "clean" / "purananuru.json").open(encoding="utf-8") as source:
    PURANANURU_CORPUS = json.load(source)

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


def test_aathichudi_exact_line_uses_its_own_shape() -> None:
    record = AATHICHUDI_CORPUS[0]
    result = Matcher(
        records=AATHICHUDI_CORPUS,
        work_id="aathichudi",
    ).verify(record["text"])

    assert result.verdict == "verified"
    assert result.matched_id == record["id"]
    assert len(normalize(record["text"]).split()) == 3


def test_auto_literature_verification_identifies_aathichudi() -> None:
    record = AATHICHUDI_CORPUS[0]

    result = verify_literature(record["text"])

    assert result["verdict"] == "verified"
    assert result["work_id"] == "aathichudi"
    assert result["work_name"] == "ஆத்திசூடி"
    assert result["matched_record"]["section"] == record["section"]


def test_auto_literature_verification_identifies_purananuru() -> None:
    record = PURANANURU_CORPUS[0]

    result = verify_literature("\n".join(record["lines"]))

    assert result["verdict"] == "verified"
    assert result["work_id"] == "purananuru"
    assert result["work_name"] == "புறநானூறு"
    assert result["matched_record"]["id"] == record["id"]
    assert result["matched_record"]["lines"] == record["lines"]


def test_purananuru_exact_text_is_verified_when_line_breaks_differ() -> None:
    record = PURANANURU_CORPUS[0]
    result = Matcher(
        records=PURANANURU_CORPUS,
        work_id="purananuru",
    ).verify(" ".join(record["lines"]))

    assert result.verdict == "verified"
    assert result.score == 100
    assert result.warning is None
    assert result.matched_id == record["id"]


def test_aathichudi_exact_text_is_verified_with_wrapped_lines() -> None:
    record = AATHICHUDI_CORPUS[0]
    result = Matcher(
        records=AATHICHUDI_CORPUS,
        work_id="aathichudi",
    ).verify("\n".join(record["text"].split()))

    assert result.verdict == "verified"
    assert result.score == 100
    assert result.warning is None
    assert result.matched_id == record["id"]


def test_non_kural_spacing_errors_return_similarity_and_word_differences() -> None:
    record = AATHICHUDI_CORPUS[0]
    changed_text = record["text"].replace("விரும்பு", "விரும்ப")
    result = Matcher(
        records=AATHICHUDI_CORPUS,
        work_id="aathichudi",
    ).verify(changed_text)

    assert result.verdict == "near_match"
    assert result.score < 100
    assert result.matched_id == record["id"]
    assert result.diff
    assert any(part.kind != "same" for part in result.diff)
    assert result.score > 90


def test_purananuru_dataset_has_explicit_source_coverage() -> None:
    present_ids = {record["id"] for record in PURANANURU_CORPUS}
    known_source_gaps = set(range(151, 161)) | {244, 267, 268, 320, 362}

    assert len(PURANANURU_CORPUS) == 385
    assert present_ids == set(range(1, 401)) - known_source_gaps
    assert all(len(record["lines"]) >= 4 for record in PURANANURU_CORPUS)


def test_every_purananuru_poem_matches_runtime_verifier() -> None:
    matcher = Matcher(records=PURANANURU_CORPUS, work_id="purananuru")

    for record in PURANANURU_CORPUS:
        result = matcher.verify("\n".join(record["lines"]))

        assert result.verdict == "verified"
        assert result.matched_id == record["id"]


def test_tolkappiyam_unavailable_is_reported_without_fallback() -> None:
    catalog = {entry["id"]: entry for entry in get_work_catalog()}

    assert catalog["tolkappiyam"]["available"] is False
    with pytest.raises(CorpusUnavailableError, match="tolkappiyam"):
        verify_literature("தமிழ் உரை", work_id="tolkappiyam")


def test_flattened_exact_couplet_is_verified_despite_missing_line_break(matcher: Matcher) -> None:
    record = CORPUS[0]
    result = matcher.verify(f"{record['line1']} {record['line2']}")
    assert result.verdict == "verified"
    assert result.score == 100
    assert result.matched_id == record["id"]
    assert result.warning == "line_structure_mismatch"


def test_exact_couplet_with_ocr_line_wrapping_is_verified(matcher: Matcher) -> None:
    record = CORPUS[0]
    words = f"{record['line1']} {record['line2']}".split()
    result = matcher.verify(f"{' '.join(words[:2])}\n{' '.join(words[2:6])}\n{words[6]}")

    assert result.verdict == "verified"
    assert result.score == 100
    assert result.matched_id == record["id"]
    assert result.warning == "line_structure_mismatch"


def test_exact_couplet_with_noncanonical_line_break_is_verified_with_warning(
    matcher: Matcher,
) -> None:
    record = CORPUS[0]
    first_line_words = record["line1"].split()
    malformed = (
        f"{' '.join(first_line_words[:3])}\n"
        f"{' '.join(first_line_words[3:])} {record['line2']}"
    )
    result = matcher.verify(malformed)
    assert result.verdict == "verified"
    assert result.score == 100
    assert result.warning == "line_structure_mismatch"


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
    assert "✅ உறுதிப்படுத்தப்பட்டது" in payload["annotated_answer"]
    assert "⚠️ அருகிய பொருத்தம்" in payload["annotated_answer"] or "❌ கிடைக்கவில்லை" in payload["annotated_answer"]
    assert ABSTAIN_MESSAGE in payload["annotated_answer"] or payload["summary"]["near"] == 1
    assert f"— குறள் {real['id']}" not in payload["annotated_answer"]


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


def test_literature_verify_endpoint_reports_detected_work() -> None:
    record = AATHICHUDI_CORPUS[0]
    response = client.post(
        "/api/literature/verify",
        json={"text": record["text"], "work_id": "all"},
    )

    assert response.status_code == 200
    assert response.json()["work_id"] == "aathichudi"
    assert response.json()["matched_record"]["text"] == record["text"]


def test_literature_verify_endpoint_verifies_flattened_kural_quote() -> None:
    record = CORPUS[0]
    response = client.post(
        "/api/literature/verify",
        json={"text": f"{record['line1']} {record['line2']}", "work_id": "thirukkural"},
    )

    assert response.status_code == 200
    assert response.json()["verdict"] == "verified"
    assert response.json()["score"] == 100
    assert response.json()["matched_record"]["id"] == record["id"]
    assert response.json()["warning"] == "line_structure_mismatch"


def test_literature_verify_endpoint_reports_purananuru() -> None:
    record = PURANANURU_CORPUS[0]
    response = client.post(
        "/api/literature/verify",
        json={"text": "\n".join(record["lines"]), "work_id": "all"},
    )

    assert response.status_code == 200
    assert response.json()["work_id"] == "purananuru"
    assert response.json()["matched_record"]["id"] == record["id"]


def test_literature_catalog_reports_installed_datasets() -> None:
    response = client.get("/api/literature/catalog")

    assert response.status_code == 200
    catalog = {record["id"]: record for record in response.json()}
    assert catalog["thirukkural"]["available"] is True
    assert catalog["aathichudi"]["entry_count"] == 109
    assert catalog["purananuru"]["available"] is True
    assert catalog["purananuru"]["entry_count"] == 385
    assert catalog["tolkappiyam"]["available"] is False


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


def test_education_catalog_returns_original_records() -> None:
    response = client.get("/api/kurals/catalog")
    assert response.status_code == 200
    catalog = response.json()
    assert len(catalog) == 1330
    assert catalog[0]["id"] == CORPUS[0]["id"]
    assert catalog[0]["paal"] == CORPUS[0]["paal"]
    assert catalog[0]["chapter_no"] == CORPUS[0]["chapter_no"]
    assert catalog[0]["chapter_name"] == CORPUS[0]["chapter_name"]
    assert catalog[0]["line1"] == CORPUS[0]["line1"]
    assert catalog[0]["line2"] == CORPUS[0]["line2"]
    assert catalog[0]["meaning_en"] == CORPUS[0]["meaning_en"]


def test_explanation_requires_server_side_provider_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(education, "GEMINI_API_KEY", "")
    education.generate_simple_explanation.cache_clear()
    response = client.post("/api/kural/1/explanation", json={"language": "en"})
    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.json()["detail"]


def test_explanation_uses_original_context_and_caches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_record = copy.deepcopy(CORPUS[0])
    monkeypatch.setattr(education, "GEMINI_API_KEY", "test-server-key")
    monkeypatch.setattr(education, "GEMINI_MODEL", "gemini-test-model")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "private reasoning", "thought": True},
                        {"text": "A simple explanation."},
                    ]
                }
            }
        ]
    }
    post = Mock(return_value=response)
    monkeypatch.setattr(education.httpx, "post", post)
    education.generate_simple_explanation.cache_clear()
    try:
        first = client.post("/api/kural/1/explanation", json={"language": "en"})
        second = client.post("/api/kural/1/explanation", json={"language": "en"})
        tamil = client.post("/api/kural/1/explanation", json={"language": "ta"})
    finally:
        education.generate_simple_explanation.cache_clear()

    assert first.status_code == second.status_code == tamil.status_code == 200
    assert first.json() == {
        "kural_id": 1,
        "language": "en",
        "explanation": "A simple explanation.",
    }
    assert second.json() == first.json()
    assert tamil.json()["language"] == "ta"
    assert post.call_count == 2
    assert post.call_args_list[0].args == (
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-test-model:generateContent",
    )
    assert post.call_args_list[0].kwargs["headers"]["x-goog-api-key"] == (
        "test-server-key"
    )
    request = post.call_args_list[0].kwargs["json"]
    prompt = request["contents"][0]["parts"][0]["text"]
    assert request["generationConfig"] == {"temperature": 0.3}
    assert CORPUS[0]["line1"] in prompt
    assert CORPUS[0]["line2"] in prompt
    assert CORPUS[0]["meaning_en"] in prompt
    assert "simple English" in request["systemInstruction"]["parts"][0]["text"]
    assert CORPUS[0] == original_record


def test_review_flagged_meaning_is_not_sent_as_verified_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = next(
        item
        for item in CORPUS
        if item["needs_human_review"] and item["meaning_en"]
    )
    monkeypatch.setattr(education, "GEMINI_API_KEY", "test-server-key")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "candidates": [
            {"content": {"parts": [{"text": "Simple explanation."}]}}
        ]
    }
    post = Mock(return_value=response)
    monkeypatch.setattr(education.httpx, "post", post)
    education.generate_simple_explanation.cache_clear()
    try:
        result = client.post(
            f"/api/kural/{record['id']}/explanation", json={"language": "ta"}
        )
    finally:
        education.generate_simple_explanation.cache_clear()

    assert result.status_code == 200
    prompt = post.call_args.kwargs["json"]["contents"][0]["parts"][0]["text"]
    assert record["meaning_en"] not in prompt
    assert "Not available." in prompt


def test_explanation_provider_error_is_safely_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import httpx

    monkeypatch.setattr(education, "GEMINI_API_KEY", "test-server-key")
    response = Mock()
    response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "provider details may contain private data",
        request=Mock(),
        response=Mock(),
    )
    monkeypatch.setattr(education.httpx, "post", Mock(return_value=response))
    education.generate_simple_explanation.cache_clear()
    try:
        result = client.post("/api/kural/1/explanation", json={"language": "ta"})
    finally:
        education.generate_simple_explanation.cache_clear()

    assert result.status_code == 503
    assert "provider details" not in result.json()["detail"]


def test_explanation_rejects_missing_kural_and_invalid_language() -> None:
    missing = client.post("/api/kural/1331/explanation", json={"language": "en"})
    invalid_language = client.post(
        "/api/kural/1/explanation", json={"language": "fr"}
    )
    assert missing.status_code == 404
    assert invalid_language.status_code == 422


def test_memory_easy_quiz_masks_one_word_and_scores_on_server() -> None:
    record = CORPUS[0]
    response = client.post(
        "/api/memory/quizzes",
        json={
            "paal": record["paal"],
            "chapter_no": record["chapter_no"],
            "difficulty": "easy",
            "range_start": record["id"],
            "range_end": record["id"],
        },
    )
    assert response.status_code == 200
    quiz = response.json()
    question = quiz["question"]
    assert question["mode"] == "easy"
    assert question["prompt"].count("_____") == 1
    assert len(question["choices"]) == 4
    assert "_answer" not in question

    server_question = memory._quizzes[quiz["id"]]["questions"][0]
    correct_index = question["choices"].index(server_question["_answer"])
    answered = client.post(
        f"/api/memory/quizzes/{quiz['id']}/answer",
        json={"question_id": question["id"], "answer_index": correct_index},
    )
    assert answered.status_code == 200
    result = answered.json()
    assert result["score"] == 10
    assert result["progress"] == {
        "current": 1,
        "total": 1,
        "attempted": 1,
        "correct": 1,
        "incorrect": 0,
    }
    assert result["complete"] is True
    assert result["last_result"]["correct"] is True
    assert client.get(f"/api/memory/quizzes/{quiz['id']}").json() == result


def test_memory_medium_quiz_accepts_harmless_formatting_and_rejects_other_verse() -> None:
    record = next(
        item for item in CORPUS if item["meaning_en"] and not item["needs_human_review"]
    )
    payload = {
        "paal": record["paal"],
        "chapter_no": record["chapter_no"],
        "difficulty": "medium",
        "range_start": record["id"],
        "range_end": record["id"],
    }
    quiz = client.post("/api/memory/quizzes", json=payload).json()
    question = quiz["question"]
    assert question["mode"] == "medium"
    assert question["prompt"] == record["meaning_en"]
    typed = unicodedata.normalize("NFD", record["line1"])
    formatted_answer = f"  {typed} !!! \n {record['line2']} , "
    answered = client.post(
        f"/api/memory/quizzes/{quiz['id']}/answer",
        json={"question_id": question["id"], "answer_text": formatted_answer},
    )
    assert answered.status_code == 200
    result = answered.json()
    assert result["score"] == 10
    assert result["progress"]["correct"] == 1
    assert result["last_result"]["accuracy"] == 100
    assert result["last_result"]["discrepancies"] == []
    assert result["last_result"]["correct_answer"] == (
        f"{record['line1']}\n{record['line2']}"
    )

    other = next(
        item for item in CORPUS
        if item["id"] != record["id"]
        and item["paal"] == record["paal"]
        and item["chapter_no"] == record["chapter_no"]
        and item["meaning_en"]
        and not item["needs_human_review"]
    )
    other_payload = {
        **payload,
        "range_start": other["id"],
        "range_end": other["id"],
    }
    other_quiz = client.post("/api/memory/quizzes", json=other_payload).json()
    rejected = client.post(
        f"/api/memory/quizzes/{other_quiz['id']}/answer",
        json={
            "question_id": other_quiz["question"]["id"],
            "answer_text": f"{record['line1']}\n{record['line2']}",
        },
    )
    assert rejected.status_code == 200
    assert rejected.json()["score"] == 0
    assert rejected.json()["progress"]["incorrect"] == 1
    assert rejected.json()["last_result"]["correct"] is False


def test_memory_hard_quiz_uses_number_and_randomized_verse_options() -> None:
    record = CORPUS[42]
    response = client.post(
        "/api/memory/quizzes",
        json={
            "paal": record["paal"],
            "chapter_no": record["chapter_no"],
            "difficulty": "hard",
            "range_start": record["id"],
            "range_end": record["id"],
        },
    )
    assert response.status_code == 200
    quiz = response.json()
    question = quiz["question"]
    assert question["prompt"] == f"Kural {record['id']}"
    assert len(question["choices"]) == 4
    assert all({"id", "line1", "line2"} == set(choice) for choice in question["choices"])
    correct_index = next(
        index for index, choice in enumerate(question["choices"])
        if choice["id"] == record["id"]
    )
    answered = client.post(
        f"/api/memory/quizzes/{quiz['id']}/answer",
        json={"question_id": question["id"], "answer_index": correct_index},
    )
    assert answered.status_code == 200
    assert answered.json()["score"] == 10
    assert answered.json()["progress"]["correct"] == 1
    assert answered.json()["last_result"]["correct_answer"] == {
        "id": record["id"],
        "line1": record["line1"],
        "line2": record["line2"],
    }


def test_memory_quiz_rejects_reusing_an_answered_question() -> None:
    record = CORPUS[0]
    quiz = client.post(
        "/api/memory/quizzes",
        json={
            "paal": record["paal"],
            "chapter_no": record["chapter_no"],
            "difficulty": "easy",
            "range_start": record["id"],
            "range_end": record["id"],
        },
    ).json()
    question = quiz["question"]
    answer = {
        "question_id": question["id"],
        "answer_index": 0,
    }
    assert client.post(f"/api/memory/quizzes/{quiz['id']}/answer", json=answer).status_code == 200
    assert client.post(f"/api/memory/quizzes/{quiz['id']}/answer", json=answer).status_code == 409
