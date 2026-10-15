#!/usr/bin/env python3
"""Generate a deterministic evaluation set and score it against the corpus."""

from __future__ import annotations

import json
import random
import re
import sys
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import (  # noqa: E402
    CORPUS_PATH,
    EVAL_DIR,
    EVAL_RESULTS_PATH,
    EVAL_SET_PATH,
    NEAR_THRESHOLD,
)
from engine.matcher import Matcher  # noqa: E402
from engine.normalize import normalize_compact  # noqa: E402

SEED = 42
WORD_RE = re.compile(r"[\u0B80-\u0BFF]+")
TAMIL_RANGE = range(0x0B80, 0x0C00)


def _read_corpus() -> list[dict[str, Any]]:
    if not CORPUS_PATH.exists():
        raise FileNotFoundError(
            "The corpus is missing. Run `python scripts/build_corpus.py` first."
        )
    with CORPUS_PATH.open(encoding="utf-8") as source:
        return json.load(source)


def _is_tamil_letter(character: str) -> bool:
    return ord(character) in TAMIL_RANGE and unicodedata.category(character).startswith("L")


def _full_text(record: dict[str, Any]) -> str:
    return f"{record['line1']}\n{record['line2']}"


def _new_case(
    case_id: str, label: str, text: str, expected_id: int | None, edit: str
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "label": label,
        "text": text,
        "expected_id": expected_id,
        "edit": edit,
    }


def _make_real_exact(
    rng: random.Random, records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    chosen = rng.sample(records, 50)
    cases: list[dict[str, Any]] = []
    for index, record in enumerate(chosen):
        if index < 25:
            text, edit = _full_text(record), "source_text"
        else:
            text = f"  {record['line1']} !!! \n   {record['line2']} ,  "
            edit = "extra_whitespace_and_punctuation"
        cases.append(
            _new_case(
                f"real_exact_{index + 1:02d}",
                "real_exact",
                text,
                int(record["id"]),
                edit,
            )
        )
    return cases


def _typo_once(text: str, rng: random.Random) -> str:
    chars = list(text)
    letter_positions = [index for index, char in enumerate(chars) if _is_tamil_letter(char)]
    if len(letter_positions) < 2:
        raise ValueError("Cannot create a Tamil character typo from this record.")
    if rng.random() < 0.65:
        del chars[rng.choice(letter_positions)]
        return "".join(chars)

    adjacent_pairs = [
        (left, right)
        for left, right in zip(letter_positions, letter_positions[1:])
        if right == left + 1
    ]
    if adjacent_pairs:
        left, right = rng.choice(adjacent_pairs)
        chars[left], chars[right] = chars[right], chars[left]
        return "".join(chars)
    del chars[rng.choice(letter_positions)]
    return "".join(chars)


def _make_real_typos(
    rng: random.Random, records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    cases = []
    for index, record in enumerate(rng.sample(records, 30)):
        original = _full_text(record)
        typo = _typo_once(original, rng)
        while normalize_compact(typo) == normalize_compact(original):
            typo = _typo_once(original, rng)
        cases.append(
            _new_case(
                f"real_typo_{index + 1:02d}",
                "real_typo",
                typo,
                int(record["id"]),
                "one_character_delete_or_swap",
            )
        )
    return cases


def _make_tricky(
    rng: random.Random, records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    cases = []
    for index, record in enumerate(rng.sample(records, 20)):
        original = _full_text(record)
        word_spans = list(WORD_RE.finditer(original))
        if not word_spans:
            raise ValueError(f"Kural {record['id']} has no Tamil words to alter.")
        for _ in range(500):
            span = rng.choice(word_spans)
            donor_record = rng.choice(records)
            if donor_record["id"] == record["id"]:
                continue
            donor_words = WORD_RE.findall(_full_text(donor_record))
            donor_word = rng.choice(donor_words)
            if donor_word == span.group():
                continue
            candidate = original[: span.start()] + donor_word + original[span.end() :]
            if normalize_compact(candidate) != normalize_compact(original):
                break
        else:
            raise ValueError("Could not create a word-swapped tricky example.")
        cases.append(
            _new_case(
                f"tricky_{index + 1:02d}",
                "tricky",
                candidate,
                int(record["id"]),
                "one_word_replaced_from_another_kural",
            )
        )
    return cases


def _all_exact_texts(records: list[dict[str, Any]]) -> set[str]:
    text_set: set[str] = set()
    for record in records:
        for text in (
            _full_text(record),
            record["line1"],
            record["line2"],
        ):
            text_set.add(normalize_compact(text))
    return text_set


def _append_fake_if_safe(
    cases: list[dict[str, Any]],
    candidate: str,
    edit: str,
    exact_texts: set[str],
) -> bool:
    if normalize_compact(candidate) in exact_texts:
        return False
    cases.append(
        _new_case(
            f"fake_{len(cases) + 1:02d}",
            "fake",
            candidate,
            None,
            edit,
        )
    )
    return True


def _make_splices(
    rng: random.Random, records: list[dict[str, Any]], exact_texts: set[str]
) -> list[dict[str, Any]]:
    by_chapter: dict[int, list[dict[str, Any]]] = {}
    for record in records:
        by_chapter.setdefault(int(record["chapter_no"]), []).append(record)

    cases: list[dict[str, Any]] = []
    for same_chapter in (True, False):
        target_count = 15
        attempts = 0
        while sum(1 for case in cases if case["edit"] == ("same_chapter_splice" if same_chapter else "cross_chapter_splice")) < target_count:
            attempts += 1
            if attempts > 2000:
                raise ValueError("Could not construct the required splice examples.")
            first = rng.choice(records)
            if same_chapter:
                options = [item for item in by_chapter[int(first["chapter_no"])] if item["id"] != first["id"]]
                if not options:
                    continue
                second = rng.choice(options)
            else:
                options = [item for item in records if item["chapter_no"] != first["chapter_no"]]
                second = rng.choice(options)
            candidate = f"{first['line1']}\n{second['line2']}"
            _append_fake_if_safe(
                cases,
                candidate,
                "same_chapter_splice" if same_chapter else "cross_chapter_splice",
                exact_texts,
            )
    return cases


def _make_word_shuffles(
    rng: random.Random,
    records: list[dict[str, Any]],
    exact_texts: set[str],
    start_number: int,
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for record in rng.sample(records, 20):
        original_words = _full_text(record).split()
        for _ in range(100):
            words = original_words.copy()
            rng.shuffle(words)
            candidate = " ".join(words)
            if normalize_compact(candidate) not in exact_texts:
                break
        else:
            raise ValueError("Could not construct a non-exact word-shuffle example.")
        _append_fake_if_safe(cases, candidate, "word_shuffle", exact_texts)
    for index, case in enumerate(cases, start_number + 1):
        case["case_id"] = f"fake_{index:02d}"
    return cases


def _load_manual_fakes() -> list[dict[str, Any]]:
    path = EVAL_DIR / "manual_fakes.json"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as source:
        payload = json.load(source)
    if not isinstance(payload, list):
        raise ValueError("eval/manual_fakes.json must be a JSON array.")
    cases = []
    for index, item in enumerate(payload, 1):
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict) and isinstance(item.get("text"), str):
            text = item["text"]
        else:
            raise ValueError(
                "Each manual fake must be a string or an object with a text field."
            )
        cases.append(
            _new_case(
                f"manual_fake_{index:02d}",
                "fake",
                text,
                None,
                "team_written_manual_fake",
            )
        )
    return cases


def build_eval_set() -> list[dict[str, Any]]:
    records = _read_corpus()
    rng = random.Random(SEED)
    exact_texts = _all_exact_texts(records)
    examples = (
        _make_real_exact(rng, records)
        + _make_real_typos(rng, records)
        + _make_tricky(rng, records)
    )
    splices = _make_splices(rng, records, exact_texts)
    shuffles = _make_word_shuffles(rng, records, exact_texts, len(splices))
    examples.extend(splices)
    examples.extend(shuffles)
    examples.extend(_load_manual_fakes())
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    EVAL_SET_PATH.write_text(
        json.dumps(
            {
                "seed": SEED,
                "base_counts": {
                    "real_exact": 50,
                    "real_typo": 30,
                    "tricky": 20,
                    "fake": 50,
                },
                "total_count": len(examples),
                "examples": examples,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return examples


def _score_results(
    examples: list[dict[str, Any]], matcher: Matcher, threshold: int
) -> tuple[dict[str, float | int], Counter[str]]:
    real = [item for item in examples if item["label"] != "fake"]
    fakes = [item for item in examples if item["label"] == "fake"]
    scored = [
        (item, matcher.verify(item["text"], item.get("expected_id")).to_dict())
        for item in examples
    ]
    verdicts: Counter[str] = Counter()
    for item, result in scored:
        if result["verdict"] == "verified":
            verdict = "verified"
        elif result["score"] >= threshold:
            verdict = "near_match"
        else:
            verdict = "not_found"
        verdicts[verdict] += 1
        item.setdefault("_scores", {})[str(threshold)] = {
            "verdict": verdict,
            "matched_id": result["matched_id"],
            "score": result["score"],
            "matched_scope": result["matched_scope"],
        }

    outcomes = [(item, item["_scores"][str(threshold)]) for item in examples]
    correct_real = sum(
        1
        for item, result in outcomes
        if item["label"] != "fake"
        and result["verdict"] in {"verified", "near_match"}
        and result["matched_id"] == item["expected_id"]
    )
    verified = [(item, result) for item, result in outcomes if result["verdict"] == "verified"]
    correct_verified = sum(
        1
        for item, result in verified
        if item["label"] == "real_exact"
        and result["matched_id"] == item["expected_id"]
    )
    tricky_total = sum(1 for item in examples if item["label"] == "tricky")
    tricky_near = sum(
        1
        for item, result in outcomes
        if item["label"] == "tricky"
        and result["verdict"] == "near_match"
        and result["matched_id"] == item["expected_id"]
    )
    fake_verified = sum(
        1
        for item, result in outcomes
        if item["label"] == "fake" and result["verdict"] == "verified"
    )
    fake_abstained = sum(
        1
        for item, result in outcomes
        if item["label"] == "fake" and result["verdict"] == "not_found"
    )
    metrics: dict[str, float | int] = {
        "false_accept_rate": fake_verified / len(fakes) if fakes else 0.0,
        "real_recall": correct_real / len(real) if real else 0.0,
        "verified_precision": correct_verified / len(verified) if verified else 0.0,
        "tricky_near_match_rate": tricky_near / tricky_total if tricky_total else 0.0,
        "fake_abstain_rate": fake_abstained / len(fakes) if fakes else 0.0,
    }
    return metrics, verdicts


def run_evaluation() -> dict[str, Any]:
    examples = build_eval_set()
    matcher = Matcher(near_threshold=0)
    # First score once; the best candidate's score is threshold-independent.
    raw_scores = [
        matcher.verify(item["text"], item.get("expected_id")).to_dict()
        for item in examples
    ]
    for item, result in zip(examples, raw_scores):
        item["_raw_match"] = {
            "verdict": result["verdict"],
            "matched_id": result["matched_id"],
            "score": result["score"],
            "matched_scope": result["matched_scope"],
        }
    threshold_sweep: list[dict[str, Any]] = []
    configured_metrics: dict[str, float | int] | None = None
    configured_verdicts: Counter[str] | None = None
    for threshold in range(60, 101):
        # Reuse the threshold-independent exact/best match rather than rescanning
        # 3,990 corpus candidates for every point in the sweep.
        for item in examples:
            raw = item["_raw_match"]
            if raw["verdict"] == "verified":
                verdict = "verified"
            elif raw["score"] >= threshold:
                verdict = "near_match"
            else:
                verdict = "not_found"
            item.setdefault("_sweep", {})[str(threshold)] = {
                **raw,
                "verdict": verdict,
            }
        saved_scores: list[dict[str, Any]] = []
        for item in examples:
            saved_scores.append(
                {
                    "verdict": item["_raw_match"]["verdict"],
                    "matched_id": item["_raw_match"]["matched_id"],
                    "score": item["_raw_match"]["score"],
                    "matched_scope": item["_raw_match"]["matched_scope"],
                }
            )
            item["_scores"] = {
                str(threshold): item["_sweep"][str(threshold)]
            }
        # Metrics helper uses the supplied results cached in _scores.
        metrics, verdicts = _metrics_from_sweep(examples, threshold)
        threshold_sweep.append({"threshold": threshold, **metrics})
        if threshold == NEAR_THRESHOLD:
            configured_metrics, configured_verdicts = metrics, verdicts

    if configured_metrics is None or configured_verdicts is None:
        configured_metrics, configured_verdicts = _metrics_from_sweep(examples, NEAR_THRESHOLD)
    dataset_counts = dict(Counter(item["label"] for item in examples))
    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "near_threshold": NEAR_THRESHOLD,
        "metrics": {
            **configured_metrics,
            "sample_counts": dataset_counts,
        },
        "threshold_sweep": threshold_sweep,
        "verdict_counts": dict(configured_verdicts),
        "dataset_counts": dataset_counts,
    }
    clean_examples = []
    for item in examples:
        clean_examples.append({key: value for key, value in item.items() if not key.startswith("_")})
    EVAL_SET_PATH.write_text(
        json.dumps(
            {
                "seed": SEED,
                "base_counts": {
                    "real_exact": 50,
                    "real_typo": 30,
                    "tricky": 20,
                    "fake": 50,
                },
                "total_count": len(clean_examples),
                "examples": clean_examples,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    EVAL_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVAL_RESULTS_PATH.write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return results


def _metrics_from_sweep(
    examples: list[dict[str, Any]], threshold: int
) -> tuple[dict[str, float], Counter[str]]:
    outcomes = [
        (item, item["_sweep"][str(threshold)])
        for item in examples
    ]
    real = [pair for pair in outcomes if pair[0]["label"] != "fake"]
    fakes = [pair for pair in outcomes if pair[0]["label"] == "fake"]
    tricky = [pair for pair in outcomes if pair[0]["label"] == "tricky"]
    verified = [pair for pair in outcomes if pair[1]["verdict"] == "verified"]
    correct_real = sum(
        result["verdict"] in {"verified", "near_match"}
        and result["matched_id"] == item["expected_id"]
        for item, result in real
    )
    correct_verified = sum(
        item["label"] == "real_exact"
        and result["matched_id"] == item["expected_id"]
        for item, result in verified
    )
    tricky_near = sum(
        result["verdict"] == "near_match"
        and result["matched_id"] == item["expected_id"]
        for item, result in tricky
    )
    fake_verified = sum(result["verdict"] == "verified" for _, result in fakes)
    fake_abstained = sum(result["verdict"] == "not_found" for _, result in fakes)
    metrics = {
        "false_accept_rate": fake_verified / len(fakes) if fakes else 0.0,
        "real_recall": correct_real / len(real) if real else 0.0,
        "verified_precision": correct_verified / len(verified) if verified else 0.0,
        "tricky_near_match_rate": tricky_near / len(tricky) if tricky else 0.0,
        "fake_abstain_rate": fake_abstained / len(fakes) if fakes else 0.0,
    }
    return metrics, Counter(result["verdict"] for _, result in outcomes)


def _print_report(results: dict[str, Any]) -> None:
    metrics = results["metrics"]
    print(f"Evaluation at NEAR_THRESHOLD={results['near_threshold']} (seed={SEED})")
    print("-" * 68)
    print(f"{'Metric':32} {'Value':>10} {'Rate':>12}")
    print("-" * 68)
    labels = [
        ("False-accept rate (fake → verified)", "false_accept_rate"),
        ("Recall on real quotations", "real_recall"),
        ("Precision of verified verdicts", "verified_precision"),
        ("Near-match rate on tricky edits", "tricky_near_match_rate"),
        ("Abstain rate on fakes", "fake_abstain_rate"),
    ]
    for label, key in labels:
        print(f"{label:32} {metrics[key]:10.3f} {metrics[key] * 100:11.1f}%")
    print("-" * 68)
    print("Threshold sweep (threshold | false-accept | real recall | tricky near | fake abstain)")
    for point in results["threshold_sweep"]:
        if point["threshold"] % 5 == 0:
            print(
                f"{point['threshold']:9d} | "
                f"{point['false_accept_rate']:.3f} | "
                f"{point['real_recall']:.3f} | "
                f"{point['tricky_near_match_rate']:.3f} | "
                f"{point['fake_abstain_rate']:.3f}"
            )


def main() -> int:
    try:
        results = run_evaluation()
    except (FileNotFoundError, ValueError, OSError, KeyError) as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        return 1
    _print_report(results)
    print(f"Results: {EVAL_RESULTS_PATH}")
    print(f"Eval set: {EVAL_SET_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
