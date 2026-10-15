"""RapidFuzz-backed local corpus matcher. It never makes network or LLM calls."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from rapidfuzz import fuzz

from config import (
    CHARACTER_WEIGHT,
    CORPUS_PATH,
    NEAR_THRESHOLD,
    WORD_OVERLAP_WEIGHT,
)
from engine.normalize import normalize, normalize_compact

Scope = Literal["full", "line1", "line2"]
Verdict = Literal["verified", "near_match", "not_found"]
EXPECTED_LINE_WORD_COUNTS = (4, 3)


@dataclass(frozen=True)
class DiffPart:
    kind: Literal["same", "changed", "input_only", "corpus_only"]
    input: str
    corpus: str


@dataclass(frozen=True)
class Verification:
    verdict: Verdict
    matched_id: int | None
    score: float
    matched_scope: Scope | None
    diff: list[DiffPart]
    claimed_id_ok: bool | None
    warning: str | None
    matched_kural: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        return result


@dataclass(frozen=True)
class IndexedText:
    record: dict[str, Any]
    scope: Scope
    text: str
    normalized: str
    compact: str


def _word_diff(input_text: str, corpus_text: str) -> list[DiffPart]:
    input_words = normalize(input_text).split()
    corpus_words = normalize(corpus_text).split()
    matcher = SequenceMatcher(a=input_words, b=corpus_words, autojunk=False)
    result: list[DiffPart] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        input_part = " ".join(input_words[i1:i2])
        corpus_part = " ".join(corpus_words[j1:j2])
        if tag == "equal":
            result.append(DiffPart("same", input_part, corpus_part))
        elif tag == "replace":
            result.append(DiffPart("changed", input_part, corpus_part))
        elif tag == "delete":
            result.append(DiffPart("input_only", input_part, ""))
        elif tag == "insert":
            result.append(DiffPart("corpus_only", "", corpus_part))
    return result


def _word_overlap(left: str, right: str) -> float:
    left_words = left.split()
    right_words = right.split()
    if not left_words or not right_words:
        return 0.0
    left_set, right_set = set(left_words), set(right_words)
    return (2 * len(left_set & right_set)) / (len(left_set) + len(right_set))


def _combined_score(query: str, candidate: str) -> float:
    character_score = float(fuzz.ratio(query, candidate))
    overlap_score = _word_overlap(query, candidate) * 100
    weight_sum = CHARACTER_WEIGHT + WORD_OVERLAP_WEIGHT
    if weight_sum <= 0:
        raise ValueError("Matching weights must have a positive sum.")
    score = (
        character_score * CHARACTER_WEIGHT
        + overlap_score * WORD_OVERLAP_WEIGHT
    ) / weight_sum
    return round(score, 2)


def _record_text(record: dict[str, Any], scope: Scope) -> str:
    if scope == "full":
        return f"{record['line1']} {record['line2']}"
    return str(record[scope])


def _word_counts_by_line(text: str) -> list[int]:
    return [
        len(words)
        for line in text.splitlines()
        if (words := normalize(line).split())
    ]


def _has_expected_couplet_shape(text: str, record: dict[str, Any]) -> bool:
    return (
        _word_counts_by_line(text) == list(EXPECTED_LINE_WORD_COUNTS)
        and _word_counts_by_line(str(record["line1"])) == [4]
        and _word_counts_by_line(str(record["line2"])) == [3]
    )


class Matcher:
    """An in-memory index of all full couplets and both half-couplets."""

    def __init__(
        self,
        corpus_path: Path = CORPUS_PATH,
        near_threshold: int = NEAR_THRESHOLD,
        records: list[dict[str, Any]] | None = None,
    ) -> None:
        if not 0 <= near_threshold <= 100:
            raise ValueError("NEAR_THRESHOLD must be between 0 and 100.")
        if records is None:
            if not corpus_path.exists():
                raise FileNotFoundError(
                    f"Local corpus not found at {corpus_path}. "
                    "Run `python scripts/build_corpus.py` first."
                )
            with corpus_path.open(encoding="utf-8") as source:
                records = json.load(source)
        self.records = records
        self.near_threshold = near_threshold
        self.by_id = {int(record["id"]): record for record in records}
        if len(self.by_id) != len(records):
            raise ValueError("The local corpus contains duplicate IDs.")
        self.index: list[IndexedText] = []
        for record in records:
            for scope in ("full", "line1", "line2"):
                text = _record_text(record, scope)  # type: ignore[arg-type]
                normalized = normalize(text)
                self.index.append(
                    IndexedText(
                        record=record,
                        scope=scope,  # type: ignore[arg-type]
                        text=text,
                        normalized=normalized,
                        compact=normalized.replace(" ", ""),
                    )
                )

    def get_kural(self, kural_id: int) -> dict[str, Any] | None:
        return self.by_id.get(kural_id)

    def verify(self, text: str, claimed_id: int | None = None) -> Verification:
        query_normalized = normalize(text)
        query_compact = query_normalized.replace(" ", "")
        if not query_compact:
            return Verification(
                "not_found", None, 0.0, None, [], None, None, None
            )

        exact_candidates = [
            item for item in self.index if item.compact == query_compact
        ]
        if exact_candidates:
            selected = self._select_claimed_candidate(exact_candidates, claimed_id)
            matched_id = int(selected.record["id"])
            if selected.scope != "full" or not _has_expected_couplet_shape(
                text, selected.record
            ):
                return Verification(
                    verdict="near_match",
                    matched_id=matched_id,
                    score=99.0,
                    matched_scope=selected.scope,
                    diff=_word_diff(text, selected.text),
                    claimed_id_ok=(
                        None if claimed_id is None else matched_id == claimed_id
                    ),
                    warning="line_word_count_mismatch",
                    matched_kural=selected.record,
                )
            return Verification(
                verdict="verified",
                matched_id=matched_id,
                score=100.0,
                matched_scope=selected.scope,
                diff=[],
                claimed_id_ok=(
                    None if claimed_id is None
                    else matched_id == claimed_id
                ),
                warning=(
                    "attribution_mismatch"
                    if claimed_id is not None
                    and matched_id != claimed_id
                    else None
                ),
                matched_kural=selected.record,
            )

        best: IndexedText | None = None
        best_score = -1.0
        for item in self.index:
            score = _combined_score(query_normalized, item.normalized)
            if score > best_score:
                best, best_score = item, score
            elif score == best_score and claimed_id is not None and item.record["id"] == claimed_id:
                if best is None or best.record["id"] != claimed_id:
                    best = item

        if best is None or best_score < self.near_threshold:
            return Verification(
                verdict="not_found",
                matched_id=None,
                score=max(0.0, best_score),
                matched_scope=None,
                diff=[],
                claimed_id_ok=None,
                warning=None,
                matched_kural=None,
            )

        matched_id = int(best.record["id"])
        return Verification(
            verdict="near_match",
            matched_id=matched_id,
            score=best_score,
            matched_scope=best.scope,
            diff=_word_diff(text, best.text),
            claimed_id_ok=(
                None if claimed_id is None else matched_id == claimed_id
            ),
            warning=(
                "attribution_mismatch"
                if claimed_id is not None and matched_id != claimed_id
                else None
            ),
            matched_kural=best.record,
        )

    @staticmethod
    def _select_claimed_candidate(
        candidates: list[IndexedText], claimed_id: int | None
    ) -> IndexedText:
        if claimed_id is not None:
            for candidate in candidates:
                if int(candidate.record["id"]) == claimed_id:
                    return candidate
        return candidates[0]


@lru_cache(maxsize=1)
def get_matcher() -> Matcher:
    return Matcher()


def verify(text: str, claimed_id: int | None = None) -> dict[str, Any]:
    """Convenience function used by the API and evaluation runner."""
    return get_matcher().verify(text, claimed_id).to_dict()
