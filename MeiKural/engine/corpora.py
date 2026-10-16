"""Registry and cross-work quote verification for the available text corpora."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from config import (
    AATHICHUDI_CORPUS_PATH,
    CORPUS_PATH,
    PURANANURU_CORPUS_PATH,
    TOLKAPPIYAM_CORPUS_PATH,
)
from engine.matcher import Matcher, Verification, get_matcher

WorkId = Literal["thirukkural", "purananuru", "tolkappiyam", "aathichudi"]
SearchWorkId = Literal["all", "thirukkural", "purananuru", "tolkappiyam", "aathichudi"]

_WORKS: tuple[tuple[WorkId, str, Path], ...] = (
    ("thirukkural", "திருக்குறள்", CORPUS_PATH),
    ("purananuru", "புறநானூறு", PURANANURU_CORPUS_PATH),
    ("tolkappiyam", "தொல்காப்பியம்", TOLKAPPIYAM_CORPUS_PATH),
    ("aathichudi", "ஆத்திசூடி", AATHICHUDI_CORPUS_PATH),
)


class CorpusUnavailableError(Exception):
    """A requested literary work has no local, usable corpus."""


@lru_cache(maxsize=1)
def get_corpus_matchers() -> dict[WorkId, Matcher]:
    matchers: dict[WorkId, Matcher] = {}
    for work_id, _, corpus_path in _WORKS:
        if work_id == "thirukkural":
            matchers[work_id] = get_matcher()
        elif corpus_path.exists():
            matchers[work_id] = Matcher(
                corpus_path=corpus_path,
                work_id=work_id,
            )
    return matchers


def get_work_catalog() -> list[dict[str, Any]]:
    matchers = get_corpus_matchers()
    entries: list[dict[str, Any]] = []
    for work_id, name, corpus_path in _WORKS:
        matcher = matchers.get(work_id)
        entries.append(
            {
                "id": work_id,
                "name": name,
                "available": matcher is not None,
                "entry_count": len(matcher.records) if matcher else 0,
                "source_file": corpus_path.name,
            }
        )
    return entries


def _serialize_result(
    work_id: WorkId, result: Verification
) -> dict[str, Any]:
    serialized = result.to_dict()
    record = serialized.pop("matched_kural")
    name = next(name for candidate_id, name, _ in _WORKS if candidate_id == work_id)
    return {
        **serialized,
        "work_id": work_id,
        "work_name": name,
        "matched_record": record,
    }


def verify_literature(
    text: str,
    work_id: SearchWorkId = "all",
    claimed_id: int | None = None,
) -> dict[str, Any]:
    matchers = get_corpus_matchers()
    if work_id != "all":
        matcher = matchers.get(work_id)
        if matcher is None:
            raise CorpusUnavailableError(
                f"The {work_id} corpus is not installed."
            )
        if claimed_id is not None and work_id != "thirukkural":
            raise ValueError("A claimed Kural number can only be used with Tirukkural.")
        return _serialize_result(
            work_id,
            matcher.verify(text, claimed_id=claimed_id),
        )

    if claimed_id is not None:
        raise ValueError("Choose Tirukkural to check a claimed Kural number.")
    if not matchers:
        raise CorpusUnavailableError("No literary corpora are installed.")

    candidates = [
        (candidate_id, matcher.verify(text))
        for candidate_id, matcher in matchers.items()
    ]
    ranked = sorted(
        candidates,
        key=lambda item: (
            item[1].verdict == "verified",
            item[1].score,
        ),
        reverse=True,
    )
    best_work_id, best_result = ranked[0]
    if best_result.verdict == "not_found":
        return {
            **best_result.to_dict(),
            "matched_kural": None,
            "work_id": None,
            "work_name": None,
            "matched_record": None,
            "searched_work_ids": [candidate_id for candidate_id, _ in candidates],
        }
    return _serialize_result(best_work_id, best_result)
