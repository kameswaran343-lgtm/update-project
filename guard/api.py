"""FastAPI endpoints for corpus lookup, verification, guarding, and evaluation."""

from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import (
    CORS_ALLOW_ORIGINS,
    EVAL_RESULTS_PATH,
    MAX_GUARD_TEXT_LENGTH,
    MAX_VERIFY_TEXT_LENGTH,
)
from engine.matcher import get_matcher
from guard.extractor import QuoteCandidate, extract_candidates

ABSTAIN_MESSAGE = (
    "Not found in the Tirukkural corpus. This cannot be confirmed as authentic. "
    "Please consult a Tamil scholar."
)


class Kural(BaseModel):
    id: int
    paal: str
    chapter_no: int
    chapter_name: str
    line1: str
    line2: str
    meaning_en: str | None
    needs_human_review: bool


class KuralVerse(BaseModel):
    id: int
    line1: str
    line2: str


class DiffPart(BaseModel):
    kind: Literal["same", "changed", "input_only", "corpus_only"]
    input: str
    corpus: str


class VerifyInput(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_VERIFY_TEXT_LENGTH)
    claimed_id: int | None = Field(default=None, ge=1, le=1330)


class GuardInput(BaseModel):
    llm_answer: str = Field(min_length=1, max_length=MAX_GUARD_TEXT_LENGTH)


class Verification(BaseModel):
    verdict: Literal["verified", "near_match", "not_found"]
    matched_id: int | None
    score: float
    matched_scope: Literal["full", "line1", "line2"] | None
    diff: list[DiffPart]
    claimed_id_ok: bool | None
    warning: str | None
    matched_kural: Kural | None


class GuardQuote(Verification):
    text: str


class GuardSummary(BaseModel):
    verified: int
    near: int
    not_found: int


class GuardResult(BaseModel):
    annotated_answer: str
    quotes: list[GuardQuote]
    summary: GuardSummary


app = FastAPI(
    title="KuralGuard API",
    description="Deterministic quotation verification against the local Tirukkural corpus.",
    version="1.0.0",
)
origins = (
    ["*"]
    if CORS_ALLOW_ORIGINS.strip() == "*"
    else [origin.strip() for origin in CORS_ALLOW_ORIGINS.split(",") if origin.strip()]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

router = APIRouter()


@router.get("/health")
@router.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/kural/{kural_id}", response_model=Kural)
def read_kural(kural_id: int) -> dict:
    if not 1 <= kural_id <= 1330:
        raise HTTPException(status_code=404, detail="Kural not found.")
    record = get_matcher().get_kural(kural_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Kural not found.")
    return record


@router.get("/kurals/verses", response_model=list[KuralVerse])
def read_kural_verses() -> list[dict[str, int | str]]:
    return [
        {"id": record["id"], "line1": record["line1"], "line2": record["line2"]}
        for record in get_matcher().records
    ]


@router.post("/verify", response_model=Verification)
def verify_quote(request: VerifyInput) -> dict:
    return get_matcher().verify(request.text, request.claimed_id).to_dict()


def _annotation(candidate: QuoteCandidate, result: dict) -> str:
    verdict = result["verdict"]
    if verdict == "verified":
        return f" ✅ verified — Kural {result['matched_id']}"
    if verdict == "near_match":
        kural = result["matched_kural"]
        real_text = f"{kural['line1']}\n{kural['line2']}" if kural else ""
        return (
            f" ⚠️ near match — possible Kural {result['matched_id']}: "
            f"{real_text}"
        )
    return f" ❌ not found — {ABSTAIN_MESSAGE}"


@router.post("/guard", response_model=GuardResult)
def guard_answer(request: GuardInput) -> dict:
    matcher = get_matcher()
    candidates = extract_candidates(request.llm_answer)
    quotes: list[dict] = []
    annotations: list[tuple[int, int, str]] = []
    counts = {"verified": 0, "near_match": 0, "not_found": 0}
    for candidate in candidates:
        result = matcher.verify(candidate.text, candidate.claimed_id).to_dict()
        counts[result["verdict"]] += 1
        quotes.append({"text": candidate.text, **result})
        annotations.append(
            (candidate.start, candidate.end, _annotation(candidate, result))
        )

    annotated = request.llm_answer
    for start, end, marker in reversed(annotations):
        annotated = annotated[:end] + marker + annotated[end:]
    return {
        "annotated_answer": annotated,
        "quotes": quotes,
        "summary": {
            "verified": counts["verified"],
            "near": counts["near_match"],
            "not_found": counts["not_found"],
        },
    }


@router.get("/eval/results")
def evaluation_results() -> dict:
    if not EVAL_RESULTS_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="Evaluation results are not built yet. Run `python eval/run_eval.py`.",
        )
    try:
        with EVAL_RESULTS_PATH.open(encoding="utf-8") as source:
            return json.load(source)
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Evaluation results are unavailable.") from exc


app.include_router(router)
app.include_router(router, prefix="/api")
