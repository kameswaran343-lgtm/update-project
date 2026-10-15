"""Server-managed memory quizzes backed by the canonical Kural corpus."""

from __future__ import annotations

import random
import re
import secrets
import threading
from difflib import SequenceMatcher
from typing import Any, Literal

from rapidfuzz import fuzz

from engine.normalize import normalize

Difficulty = Literal["easy", "medium", "hard"]
QUESTION_COUNT = 10
POINTS_PER_QUESTION = 10
MEDIUM_ACCEPTANCE_PERCENT = 82

_quizzes: dict[str, dict[str, Any]] = {}
_quizzes_lock = threading.Lock()


def _random_question_id() -> str:
    return secrets.token_urlsafe(12)


def _masked_verse(record: dict[str, Any]) -> tuple[str, str]:
    lines = [str(record["line1"]), str(record["line2"])]
    words = [
        (line_index, match.start(), match.end(), match.group())
        for line_index, line in enumerate(lines)
        for match in re.finditer(r"\S+", line)
    ]
    if not words:
        raise ValueError(f"Kural {record['id']} has no words to mask.")
    line_index, start, end, missing_word = random.choice(words)
    lines[line_index] = f"{lines[line_index][:start]}_____{lines[line_index][end:]}"
    return "\n".join(lines), missing_word


def _make_question(
    record: dict[str, Any],
    difficulty: Difficulty,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    question_id = _random_question_id()
    if difficulty == "easy":
        prompt, answer = _masked_verse(record)
        word_pool = {
            word
            for item in records
            for line in (item["line1"], item["line2"])
            for word in line.split()
            if word != answer
        }
        distractors = random.sample(list(word_pool), min(3, len(word_pool)))
        choices = [answer, *distractors]
        random.shuffle(choices)
        return {
            "id": question_id,
            "mode": difficulty,
            "prompt": prompt,
            "choices": choices,
            "_answer": answer,
        }
    if difficulty == "medium":
        return {
            "id": question_id,
            "mode": difficulty,
            "prompt": record["meaning_en"],
            "_answer": f"{record['line1']}\n{record['line2']}",
        }

    distractor_pool = [
        item
        for item in records
        if item["id"] != record["id"]
        and (item["paal"] == record["paal"] or item["chapter_no"] == record["chapter_no"])
        and (item["line1"], item["line2"]) != (record["line1"], record["line2"])
    ]
    if len(distractor_pool) < 3:
        distractor_pool = [
            item
            for item in records
            if item["id"] != record["id"]
            and (item["line1"], item["line2"]) != (record["line1"], record["line2"])
        ]
    choices = random.sample(distractor_pool, min(3, len(distractor_pool)))
    choices.append(record)
    random.shuffle(choices)
    return {
        "id": question_id,
        "mode": difficulty,
        "prompt": f"Kural {record['id']}",
        "choices": [
            {
                "id": choice["id"],
                "line1": choice["line1"],
                "line2": choice["line2"],
            }
            for choice in choices
        ],
        "_answer": record["id"],
    }


def _public_question(question: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in question.items() if not key.startswith("_")}


def _state(quiz: dict[str, Any]) -> dict[str, Any]:
    current = quiz["questions"][quiz["index"]] if quiz["index"] < len(quiz["questions"]) else None
    attempted = quiz["correct"] + quiz["incorrect"]
    return {
        "id": quiz["id"],
        "difficulty": quiz["difficulty"],
        "scope": quiz["scope"],
        "question": _public_question(current) if current else None,
        "progress": {
            "current": min(quiz["index"] + 1, len(quiz["questions"])),
            "total": len(quiz["questions"]),
            "attempted": attempted,
            "correct": quiz["correct"],
            "incorrect": quiz["incorrect"],
        },
        "score": quiz["score"],
        "complete": current is None,
        "last_result": quiz["last_result"],
    }


def create_quiz(
    records: list[dict[str, Any]],
    *,
    paal: str,
    chapter_no: int,
    difficulty: Difficulty,
    range_start: int | None = None,
    range_end: int | None = None,
) -> dict[str, Any]:
    if (range_start is None) != (range_end is None):
        raise ValueError("Provide both ends of the Kural range or leave both blank.")
    if range_start is not None and range_end is not None and range_start > range_end:
        raise ValueError("The Kural range start must not be after its end.")

    scoped = [
        record
        for record in records
        if record["paal"] == paal
        and record["chapter_no"] == chapter_no
        and (range_start is None or range_start <= record["id"] <= range_end)
    ]
    if range_start is not None and range_end is not None:
        scoped = [
            record for record in scoped
            if range_start <= record["id"] <= range_end
        ]
    if not scoped:
        raise ValueError("No Kurals are available in the selected learning scope.")

    if difficulty == "medium":
        scoped = [
            record
            for record in scoped
            if record.get("meaning_en") and not record.get("needs_human_review")
        ]
        if not scoped:
            raise ValueError(
                "No verified English meanings are available in this learning scope."
            )

    selected = random.sample(scoped, min(QUESTION_COUNT, len(scoped)))
    quiz_id = secrets.token_urlsafe(32)
    quiz = {
        "id": quiz_id,
        "difficulty": difficulty,
        "scope": {
            "paal": paal,
            "chapter_no": chapter_no,
            "chapter_name": scoped[0]["chapter_name"],
            "range_start": range_start,
            "range_end": range_end,
        },
        "questions": [
            _make_question(record, difficulty, records) for record in selected
        ],
        "index": 0,
        "score": 0,
        "correct": 0,
        "incorrect": 0,
        "last_result": None,
    }
    with _quizzes_lock:
        _quizzes[quiz_id] = quiz
    return _state(quiz)


def get_quiz(quiz_id: str) -> dict[str, Any] | None:
    with _quizzes_lock:
        quiz = _quizzes.get(quiz_id)
        return _state(quiz) if quiz else None


def _medium_accuracy(answer: str, canonical: str) -> tuple[int, list[dict[str, str]]]:
    typed = normalize(answer)
    expected = normalize(canonical)
    typed_compact = typed.replace(" ", "")
    expected_compact = expected.replace(" ", "")
    accuracy = (
        round(fuzz.ratio(typed_compact, expected_compact))
        if typed_compact and expected_compact
        else 0
    )
    matcher = SequenceMatcher(a=typed.split(), b=expected.split(), autojunk=False)
    discrepancies = []
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        discrepancies.append({
            "kind": tag,
            "answer": " ".join(typed.split()[left_start:left_end]),
            "correct": " ".join(expected.split()[right_start:right_end]),
        })
    return accuracy, discrepancies


def answer_quiz(
    quiz_id: str,
    *,
    question_id: str,
    answer_index: int | None = None,
    answer_text: str | None = None,
) -> dict[str, Any] | None:
    with _quizzes_lock:
        quiz = _quizzes.get(quiz_id)
        if not quiz:
            return None
        if quiz["index"] >= len(quiz["questions"]):
            raise ValueError("This quiz is already complete.")
        question = quiz["questions"][quiz["index"]]
        if question["id"] != question_id:
            raise ValueError("This question has already been answered or is no longer current.")

        difficulty: Difficulty = quiz["difficulty"]
        if difficulty == "medium":
            if answer_text is None or not answer_text.strip():
                raise ValueError("Enter the Kural before submitting your answer.")
            accuracy, discrepancies = _medium_accuracy(answer_text, question["_answer"])
            is_correct = accuracy >= MEDIUM_ACCEPTANCE_PERCENT
            points = round(accuracy * POINTS_PER_QUESTION / 100) if is_correct else 0
            feedback = {
                "correct": is_correct,
                "points": points,
                "accuracy": accuracy,
                "correct_answer": question["_answer"],
                "discrepancies": discrepancies,
            }
        else:
            choices = question["choices"]
            if answer_index is None or not 0 <= answer_index < len(choices):
                raise ValueError("Select one of the available answers.")
            if difficulty == "easy":
                is_correct = choices[answer_index] == question["_answer"]
                correct_answer: Any = question["_answer"]
            else:
                is_correct = choices[answer_index]["id"] == question["_answer"]
                correct_answer = next(
                    choice for choice in choices if choice["id"] == question["_answer"]
                )
            points = POINTS_PER_QUESTION if is_correct else 0
            feedback = {
                "correct": is_correct,
                "points": points,
                "correct_answer": correct_answer,
            }

        feedback["question_id"] = question_id
        quiz["correct" if is_correct else "incorrect"] += 1
        quiz["score"] += points
        quiz["last_result"] = feedback
        quiz["index"] += 1
        return _state(quiz)
