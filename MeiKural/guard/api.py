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
from engine.corpora import (
    CorpusUnavailableError,
    SearchWorkId,
    WorkId,
    get_work_catalog,
    verify_literature,
)
from engine.matcher import get_matcher
from guard.education import (
    ExplanationUnavailableError,
    generate_simple_explanation,
)
from guard.extractor import QuoteCandidate, extract_candidates
from guard import memory

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


class ExplanationInput(BaseModel):
    language: Literal["ta", "en"]


class ExplanationResult(BaseModel):
    kural_id: int
    language: Literal["ta", "en"]
    explanation: str


class MemoryQuizInput(BaseModel):
    paal: str = Field(min_length=1, max_length=100)
    chapter_no: int = Field(ge=1, le=133)
    difficulty: Literal["easy", "medium", "hard"]
    range_start: int | None = Field(default=None, ge=1, le=1330)
    range_end: int | None = Field(default=None, ge=1, le=1330)


class MemoryAnswerInput(BaseModel):
    question_id: str = Field(min_length=1, max_length=100)
    answer_index: int | None = Field(default=None, ge=0)
    answer_text: str | None = Field(default=None, max_length=2000)


class DiffPart(BaseModel):
    kind: Literal["same", "changed", "input_only", "corpus_only"]
    input: str
    corpus: str


class VerifyInput(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_VERIFY_TEXT_LENGTH)
    claimed_id: int | None = Field(default=None, ge=1, le=1330)


class LiteratureVerifyInput(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_VERIFY_TEXT_LENGTH)
    work_id: SearchWorkId = "all"
    claimed_id: int | None = Field(default=None, ge=1, le=1330)


class LiteratureWork(BaseModel):
    id: WorkId
    name: str
    available: bool
    entry_count: int
    source_file: str


class LiteratureVerification(BaseModel):
    verdict: Literal["verified", "near_match", "not_found"]
    matched_id: int | None
    score: float
    matched_scope: Literal["full", "line1", "line2"] | None
    diff: list[DiffPart]
    claimed_id_ok: bool | None
    warning: str | None
    work_id: WorkId | None
    work_name: str | None
    matched_record: dict | None
    searched_work_ids: list[WorkId] | None = None


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


@router.get("/kurals/catalog", response_model=list[Kural])
def read_kural_catalog() -> list[dict]:
    return get_matcher().records


@router.get("/literature/catalog", response_model=list[LiteratureWork])
def read_literature_catalog() -> list[dict]:
    return get_work_catalog()


@router.post("/literature/verify", response_model=LiteratureVerification)
def verify_literary_quote(request: LiteratureVerifyInput) -> dict:
    try:
        return verify_literature(
            request.text,
            work_id=request.work_id,
            claimed_id=request.claimed_id,
        )
    except CorpusUnavailableError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/memory/quizzes")
def start_memory_quiz(request: MemoryQuizInput) -> dict:
    try:
        return memory.create_quiz(
            get_matcher().records,
            paal=request.paal,
            chapter_no=request.chapter_no,
            difficulty=request.difficulty,
            range_start=request.range_start,
            range_end=request.range_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/memory/quizzes/{quiz_id}")
def read_memory_quiz(quiz_id: str) -> dict:
    quiz = memory.get_quiz(quiz_id)
    if quiz is None:
        raise HTTPException(
            status_code=404,
            detail="This quiz session is no longer available. Start a new quiz.",
        )
    return quiz


@router.post("/memory/quizzes/{quiz_id}/answer")
def answer_memory_quiz(quiz_id: str, request: MemoryAnswerInput) -> dict:
    try:
        result = memory.answer_quiz(
            quiz_id,
            question_id=request.question_id,
            answer_index=request.answer_index,
            answer_text=request.answer_text,
        )
    except ValueError as exc:
        status_code = 409 if "already been answered" in str(exc) or "already complete" in str(exc) else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="This quiz session is no longer available. Start a new quiz.",
        )
    return result


@router.post(
    "/kural/{kural_id}/explanation", response_model=ExplanationResult
)
def explain_kural(
    kural_id: int, request: ExplanationInput
) -> ExplanationResult:
    if not 1 <= kural_id <= 1330:
        raise HTTPException(status_code=404, detail="Kural not found.")
    record = get_matcher().get_kural(kural_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Kural not found.")
    try:
        explanation = generate_simple_explanation(
            kural_id,
            request.language,
            record["line1"],
            record["line2"],
            record.get("meaning_en") if not record.get("needs_human_review") else "",
        )
    except ExplanationUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ExplanationResult(
        kural_id=kural_id,
        language=request.language,
        explanation=explanation,
    )


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
