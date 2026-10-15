#!/usr/bin/env python3
"""Fetch, cross-check, normalize, and validate the local Kural corpus.

Raw downloads are immutable: an existing raw file is always reused and never
rewritten. To archive a newer upstream snapshot, choose a new file name and
update the source configuration intentionally.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import sys
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import (  # noqa: E402
    DATA_CLEAN_DIR,
    DATA_RAW_DIR,
    SOURCE_A_DETAIL_URL,
    SOURCE_A_VERSES_URL,
    SOURCE_B_FALLBACK_URL,
    SOURCE_B_PRIMARY_URL,
    SOURCE_TIMEOUT_SECONDS,
)

USER_AGENT = "KuralGuard-corpus-builder/1.0 (open-source hackathon MVP)"
EXPECTED_KURAL_COUNT = 1330
EXPECTED_CHAPTER_COUNT = 133


class CorpusBuildError(RuntimeError):
    """Raised when the corpus cannot be built safely from fetched sources."""


def _request_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=SOURCE_TIMEOUT_SECONDS) as response:
        if response.status != 200:
            raise CorpusBuildError(f"Unexpected HTTP status {response.status} for {url}")
        return response.read()


def _load_json_bytes(raw: bytes, source_name: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusBuildError(f"Could not parse {source_name} as UTF-8 JSON: {exc}") from exc


def _fetch_immutable(url: str, destination: Path) -> bytes:
    """Download a source once; later runs use those exact bytes unchanged."""
    if destination.exists():
        return destination.read_bytes()
    raw = _request_bytes(url)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("xb") as output:
            output.write(raw)
    except FileExistsError:
        # Another builder may have won the race. Preserve and use its raw file.
        return destination.read_bytes()
    return raw


def _load_primary_api_record(kural_id: int) -> tuple[bytes, dict[str, Any]]:
    url = SOURCE_B_PRIMARY_URL.format(id=kural_id)
    raw = _request_bytes(url)
    value = _load_json_bytes(raw, f"primary API response for Kural {kural_id}")
    if isinstance(value, list):
        if len(value) != 1:
            raise CorpusBuildError(
                f"Primary API returned {len(value)} items for Kural {kural_id}."
            )
        value = value[0]
    if not isinstance(value, dict):
        raise CorpusBuildError(f"Primary API response for Kural {kural_id} is not an object.")
    return raw, value


def _fetch_primary_api() -> tuple[Path, list[dict[str, Any]]] | None:
    """Try the requested per-ID API and archive each original response as JSONL."""
    try:
        first_raw, first_record = _load_primary_api_record(1)
    except (urllib.error.URLError, TimeoutError, OSError, CorpusBuildError) as exc:
        print(
            "Primary API unavailable; trying the configured independent API fallback "
            f"({type(exc).__name__}: {exc}).",
            file=sys.stderr,
        )
        return None

    responses: dict[int, tuple[bytes, dict[str, Any]]] = {1: (first_raw, first_record)}
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            future_ids = {
                pool.submit(_load_primary_api_record, kural_id): kural_id
                for kural_id in range(2, EXPECTED_KURAL_COUNT + 1)
            }
            for future in concurrent.futures.as_completed(future_ids):
                kural_id = future_ids[future]
                responses[kural_id] = future.result()
    except (urllib.error.URLError, TimeoutError, OSError, CorpusBuildError) as exc:
        print(
            "Primary API did not provide a complete 1,330-record snapshot; "
            f"trying the configured independent API fallback ({type(exc).__name__}: {exc}).",
            file=sys.stderr,
        )
        return None

    path = DATA_RAW_DIR / "source_b_api_thirukkural.jsonl"
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_lines = [responses[kural_id][0].rstrip(b"\r\n") for kural_id in range(1, EXPECTED_KURAL_COUNT + 1)]
    if not path.exists():
        try:
            with path.open("xb") as output:
                output.write(b"\n".join(raw_lines) + b"\n")
        except FileExistsError:
            pass
    parsed = [responses[kural_id][1] for kural_id in range(1, EXPECTED_KURAL_COUNT + 1)]
    return path, parsed


def _get_api_lines(record: dict[str, Any]) -> tuple[int, str, str]:
    kural_id = record.get("id", record.get("number", record.get("Number")))
    if kural_id is None:
        raise CorpusBuildError(f"API record has no Kural ID: {record!r}")
    text: Any = record.get("kural", record.get("tamil", record.get("couplet")))
    if text is not None:
        if isinstance(text, list) and len(text) >= 2:
            line1, line2 = text[0], text[1]
        elif isinstance(text, str):
            if "$" in text:
                parts = text.split("$", 1)
            elif "\n" in text:
                parts = text.split("\n", 1)
            else:
                parts = []
            if len(parts) != 2:
                raise CorpusBuildError(
                    f"API text for Kural {kural_id} has no recognized line separator."
                )
            line1, line2 = parts
        else:
            line1 = line2 = None
    else:
        line1 = record.get("line1", record.get("Line1", record.get("kural_line1")))
        line2 = record.get("line2", record.get("Line2", record.get("kural_line2")))
    if not isinstance(line1, str) or not isinstance(line2, str):
        raise CorpusBuildError(f"API record for Kural {kural_id} has no two Tamil lines.")
    return int(kural_id), line1.strip(), line2.strip()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CorpusBuildError(f"Invalid JSONL in {path} at line {line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise CorpusBuildError(f"Expected an object in {path} at line {line_number}.")
        rows.append(row)
    return rows


def _load_secondary_source() -> tuple[str, list[dict[str, Any]]]:
    primary_path = DATA_RAW_DIR / "source_b_api_thirukkural.jsonl"
    if primary_path.exists():
        return primary_path.name, _load_jsonl(primary_path)

    fallback_path = DATA_RAW_DIR / "source_b_senkanthal_kural.json"
    if fallback_path.exists():
        raw = fallback_path.read_bytes()
        payload = _load_json_bytes(raw, fallback_path.name)
    else:
        try:
            primary_result = _fetch_primary_api()
        except Exception as exc:
            print(
                "Primary API download failed; trying the configured independent API "
                f"fallback ({type(exc).__name__}: {exc}).",
                file=sys.stderr,
            )
            primary_result = None
        if primary_result is not None:
            path, records = primary_result
            return path.name, records
        try:
            raw = _fetch_immutable(SOURCE_B_FALLBACK_URL, fallback_path)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise CorpusBuildError(
                "Could not fetch a second independent source. The requested API is "
                "unavailable and the configured fallback could not be reached; "
                "no cleaned corpus was written."
            ) from exc
        payload = _load_json_bytes(raw, fallback_path.name)

    if not isinstance(payload, list):
        raise CorpusBuildError("The secondary API must provide a list of Kural records.")
    return fallback_path.name, payload


def _nfc(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def _canonical_line(value: str) -> str:
    return " ".join(_nfc(value).split())


def _chapter_metadata(detail_payload: Any) -> dict[int, dict[str, str | int]]:
    if isinstance(detail_payload, list):
        if len(detail_payload) != 1:
            raise CorpusBuildError("Source A detail.json should contain one root object.")
        root = detail_payload[0]
    else:
        root = detail_payload
    try:
        sections = root["section"]["detail"]
    except (TypeError, KeyError) as exc:
        raise CorpusBuildError("Could not find the paal/chapter structure in detail.json.") from exc

    chapters: dict[int, dict[str, str | int]] = {}
    for section in sections:
        paal_name = _nfc(str(section["name"]))
        for group in section["chapterGroup"]["detail"]:
            for chapter in group["chapters"]["detail"]:
                chapter_no = int(chapter["number"])
                start, end = int(chapter["start"]), int(chapter["end"])
                chapter_name = _nfc(str(chapter["name"]))
                for kural_id in range(start, end + 1):
                    if kural_id in chapters:
                        raise CorpusBuildError(
                            f"Source A chapter metadata assigns Kural {kural_id} twice."
                        )
                    chapters[kural_id] = {
                        "paal": paal_name,
                        "chapter_no": chapter_no,
                        "chapter_name": chapter_name,
                    }
    if len(chapters) != EXPECTED_KURAL_COUNT:
        raise CorpusBuildError(
            f"Chapter metadata covers {len(chapters)} couplets, expected 1,330."
        )
    return chapters


def _validate(couplets: list[dict[str, Any]]) -> None:
    if len(couplets) != EXPECTED_KURAL_COUNT:
        raise CorpusBuildError(f"Expected 1,330 couplets, got {len(couplets)}.")
    ids = [item["id"] for item in couplets]
    if len(set(ids)) != EXPECTED_KURAL_COUNT or set(ids) != set(
        range(1, EXPECTED_KURAL_COUNT + 1)
    ):
        raise CorpusBuildError("Corpus IDs must be unique and cover exactly 1..1330.")
    chapter_counts: dict[int, int] = {}
    for item in couplets:
        if not item["line1"].strip() or not item["line2"].strip():
            raise CorpusBuildError(f"Kural {item['id']} has an empty line.")
        chapter_no = int(item["chapter_no"])
        if not 1 <= chapter_no <= EXPECTED_CHAPTER_COUNT:
            raise CorpusBuildError(
                f"Kural {item['id']} has invalid chapter number {chapter_no}."
            )
        chapter_counts[chapter_no] = chapter_counts.get(chapter_no, 0) + 1
    if set(chapter_counts) != set(range(1, EXPECTED_CHAPTER_COUNT + 1)):
        raise CorpusBuildError("Corpus must cover exactly chapters 1..133.")
    wrong_chapters = {
        chapter: count for chapter, count in chapter_counts.items() if count != 10
    }
    if wrong_chapters:
        raise CorpusBuildError(
            f"Expected 10 couplets in every chapter; invalid counts: {wrong_chapters}"
        )


def build_corpus() -> tuple[int, str]:
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    DATA_CLEAN_DIR.mkdir(parents=True, exist_ok=True)

    verses_path = DATA_RAW_DIR / "source_a_thirukkural.json"
    detail_path = DATA_RAW_DIR / "source_a_detail.json"
    verses_payload = _load_json_bytes(
        _fetch_immutable(SOURCE_A_VERSES_URL, verses_path), verses_path.name
    )
    detail_payload = _load_json_bytes(
        _fetch_immutable(SOURCE_A_DETAIL_URL, detail_path), detail_path.name
    )
    if not isinstance(verses_payload, dict) or not isinstance(verses_payload.get("kural"), list):
        raise CorpusBuildError("Source A thirukkural.json does not have its documented kural array.")
    source_a_rows = verses_payload["kural"]
    source_b_name, source_b_rows = _load_secondary_source()
    metadata = _chapter_metadata(detail_payload)

    source_a: dict[int, dict[str, Any]] = {}
    for row in source_a_rows:
        try:
            kural_id = int(row["Number"])
            line1, line2 = row["Line1"], row["Line2"]
        except (KeyError, TypeError, ValueError) as exc:
            raise CorpusBuildError(f"Invalid Source A verse record: {row!r}") from exc
        if kural_id in source_a:
            raise CorpusBuildError(f"Source A contains duplicate Kural ID {kural_id}.")
        if not isinstance(line1, str) or not isinstance(line2, str):
            raise CorpusBuildError(f"Source A Kural {kural_id} has non-string lines.")
        source_a[kural_id] = {
            "line1": _nfc(line1),
            "line2": _nfc(line2),
            "meaning_en": (
                _nfc(str(row["Translation"])) if row.get("Translation") else None
            ),
        }

    source_b: dict[int, tuple[str, str]] = {}
    for row in source_b_rows:
        if not isinstance(row, dict):
            raise CorpusBuildError(f"Invalid record in {source_b_name}: {row!r}")
        kural_id, line1, line2 = _get_api_lines(row)
        if kural_id in source_b:
            raise CorpusBuildError(f"Secondary source contains duplicate Kural ID {kural_id}.")
        source_b[kural_id] = (_nfc(line1), _nfc(line2))
    expected_ids = set(range(1, EXPECTED_KURAL_COUNT + 1))
    if set(source_a) != expected_ids:
        raise CorpusBuildError(
            f"Source A must contain exactly IDs 1..1330 (got {len(source_a)} records)."
        )
    if set(source_b) != expected_ids:
        raise CorpusBuildError(
            f"Secondary source must contain exactly IDs 1..1330 (got {len(source_b)} records)."
        )

    couplets: list[dict[str, Any]] = []
    mismatch_path = DATA_CLEAN_DIR / "mismatches.csv"
    mismatch_rows: list[dict[str, Any]] = []
    for kural_id in range(1, EXPECTED_KURAL_COUNT + 1):
        a = source_a[kural_id]
        b_line1, b_line2 = source_b[kural_id]
        metadata_row = metadata[kural_id]
        agrees = (
            _canonical_line(a["line1"]) == _canonical_line(b_line1)
            and _canonical_line(a["line2"]) == _canonical_line(b_line2)
        )
        needs_review = not agrees
        if needs_review:
            mismatch_rows.append(
                {
                    "id": kural_id,
                    "source_a_line1": a["line1"],
                    "source_a_line2": a["line2"],
                    "source_b_line1": b_line1,
                    "source_b_line2": b_line2,
                    "resolution": "source_a_no_majority",
                    "needs_human_review": True,
                }
            )
        couplets.append(
            {
                "id": kural_id,
                "paal": metadata_row["paal"],
                "chapter_no": metadata_row["chapter_no"],
                "chapter_name": metadata_row["chapter_name"],
                # With two sources, a disagreement is a tie. The task requires
                # Source A to win ties and asks us to flag them for review.
                "line1": a["line1"],
                "line2": a["line2"],
                "meaning_en": a["meaning_en"],
                "needs_human_review": needs_review,
            }
        )

    _validate(couplets)
    with mismatch_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "id",
                "source_a_line1",
                "source_a_line2",
                "source_b_line1",
                "source_b_line2",
                "resolution",
                "needs_human_review",
            ],
        )
        writer.writeheader()
        writer.writerows(mismatch_rows)

    corpus_path = DATA_CLEAN_DIR / "kural.json"
    corpus_path.write_text(
        json.dumps(couplets, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(mismatch_rows), source_b_name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        mismatch_count, source_b_name = build_corpus()
    except (CorpusBuildError, urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"Corpus build failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Built and validated {EXPECTED_KURAL_COUNT} couplets across "
        f"{EXPECTED_CHAPTER_COUNT} chapters. Source B: {source_b_name}; "
        f"{mismatch_count} disagreements require human review."
    )
    print(f"Clean corpus: {DATA_CLEAN_DIR / 'kural.json'}")
    print(f"Mismatch report: {DATA_CLEAN_DIR / 'mismatches.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
