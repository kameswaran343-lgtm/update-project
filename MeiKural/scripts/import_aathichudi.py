#!/usr/bin/env python3
"""Normalize the licensed Aathichudi source file into the local corpus format."""

from __future__ import annotations

import json
import sys
from urllib.request import urlopen
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import AATHICHUDI_CORPUS_PATH, DATA_RAW_DIR  # noqa: E402

SOURCE_PATH = DATA_RAW_DIR / "source_aathichudi.json"
SOURCE_DOWNLOAD_URL = (
    "https://raw.githubusercontent.com/tamizhilakkiyam/aathichudi/"
    "77896642fae2d72d46ddee6c339f2b0ae25c48fe/public/aathichudi.json"
)
SOURCE_ATTRIBUTION_URL = (
    "https://github.com/tamizhilakkiyam/aathichudi/blob/"
    "77896642fae2d72d46ddee6c339f2b0ae25c48fe/public/aathichudi.json"
)
EXPECTED_COUNT = 109


def _validate_source(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or not isinstance(value.get("lines"), list):
        raise ValueError("Aathichudi source must contain a `lines` array.")
    lines = value["lines"]
    if len(lines) != EXPECTED_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_COUNT} Aathichudi entries, got {len(lines)}."
        )

    sections = value.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("Aathichudi source must contain section ranges.")
    normalized_sections: list[dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("Aathichudi sections must be objects.")
        name = section.get("name")
        bounds = section.get("lines")
        if (
            not isinstance(name, str)
            or not name.strip()
            or not isinstance(bounds, list)
            or len(bounds) != 2
            or not all(isinstance(bound, int) for bound in bounds)
        ):
            raise ValueError("Each Aathichudi section needs a name and line range.")
        start, end = bounds
        if not 1 <= start <= end <= EXPECTED_COUNT:
            raise ValueError(f"Invalid Aathichudi section range: {bounds!r}.")
        normalized_sections.append({"name": name.strip(), "start": start, "end": end})

    result: list[dict[str, Any]] = []
    for number, item in enumerate(lines, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Aathichudi entry {number} is not an object.")
        text = item.get("li")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Aathichudi entry {number} has no text.")
        section_names = [
            section["name"]
            for section in normalized_sections
            if section["start"] <= number <= section["end"]
        ]
        if len(section_names) != 1:
            raise ValueError(
                f"Aathichudi entry {number} must belong to exactly one section."
            )
        result.append(
            {
                "id": number,
                "section": section_names[0],
                "text": text.strip(),
                "meaning_ta": item.get("mng"),
                "paraphrase_ta": item.get("pph"),
                "translation_en": item.get("tl"),
                "source_url": SOURCE_ATTRIBUTION_URL,
            }
        )
    return result


def build_corpus() -> int:
    if SOURCE_PATH.exists():
        with SOURCE_PATH.open(encoding="utf-8") as source:
            payload = json.load(source)
    else:
        with urlopen(SOURCE_DOWNLOAD_URL, timeout=20) as response:
            payload = json.load(response)
    records = _validate_source(payload)
    AATHICHUDI_CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    AATHICHUDI_CORPUS_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return len(records)


if __name__ == "__main__":
    print(f"Built {build_corpus()} Aathichudi entries at {AATHICHUDI_CORPUS_PATH}.")
