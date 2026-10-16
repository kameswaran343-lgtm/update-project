#!/usr/bin/env python3
"""Build Purananuru records from the CC BY-SA Wikisource transcription."""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import PURANANURU_CORPUS_PATH  # noqa: E402

API_URL = "https://ta.wikisource.org/w/api.php"
WIKISOURCE_ROOT = "https://ta.wikisource.org"
CICT_SCAN_URL = "https://library.cict.in/api/storage/ebooks/PURA-CICT__1_.pdf"
LICENSE = "CC BY-SA 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-sa/4.0/"
WORK_TITLE = "புறநானூறு"
KNOWN_SOURCE_GAPS = set(range(151, 161)) | {244, 267, 268, 320, 362}
EXPECTED_POEM_IDS = set(range(1, 401)) - KNOWN_SOURCE_GAPS
POEM_HEADING = re.compile(
    r"^=+\s*பாடல்\s*[:：]\s*(\d+)\b(.*?)=+\s*$",
    flags=re.MULTILINE,
)
STANZA = re.compile(r"^#[ \t]*(.*?)(?=^\s*$|\Z)", flags=re.MULTILINE | re.DOTALL)
POEM_TAG = re.compile(r"<poem>(.*?)(?=</poem>|<poem>|\Z)", re.DOTALL)
POEM_ID_LINE = re.compile(
    r"^\s*(?:</poem>\s*)?(?:பாடல்\s*[:：]?\s*|v\s*)?"
    r"(\d{1,3})(?:\s+[^0-9].*)?\s*$"
)
NUMBERED_TITLE_LINE = re.compile(r"^=+\s*(\d{1,3})[.．]\s*(.*?)\s*=+\s*$")
TRAILING_NUMBER_TITLE_LINE = re.compile(r"^=+\s*(.*?)\s*=+\s*(\d{1,3})\s*$")
TITLE_LINE = re.compile(r"^=+\s*(.*?)\s*=+$")
LINE_NUMBERED_VERSE = re.compile(r"^\s*:\s*(?:\d+\s*)?(.*?)\s*$")
LINE_NUMBER_MARKER = re.compile(r"(?m)^\s*:\s*\d+\s+\S")
METADATA_LABEL = re.compile(
    r"^[;=:\s]*(?:பாடியவர்|பாடியோர்|பாடப்பட்டோன்|பாடப்பட்டோர்|திணை|துறை|"
    r"குறிப்பு|சிறப்பு)(?:\s*[:：;]\s*|\s+)",
    flags=re.MULTILINE,
)


def _source_pages() -> list[str]:
    return [
        f"{WORK_TITLE}/பாடல் {start:02d}-{min(start + 9, 400):02d}"
        for start in range(1, 401, 10)
    ]


def _fetch_wikisource_pages() -> list[dict[str, Any]]:
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if curl is None:
        raise FileNotFoundError(
            "curl is required to download the public Wikisource transcription."
        )

    params = urlencode(
        {
            "action": "query",
            "prop": "revisions",
            "rvprop": "ids|content",
            "rvslots": "main",
            "titles": "|".join(_source_pages()),
            "format": "json",
            "formatversion": "2",
        }
    )
    response = subprocess.run(
        [
            curl,
            "--location",
            "--fail",
            "--silent",
            "--show-error",
            "--max-time",
            "120",
            "--retry",
            "3",
            "--retry-delay",
            "10",
            "--user-agent",
            "MeiKural corpus importer/1.0",
            f"{API_URL}?{params}",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if response.returncode:
        raise RuntimeError(
            "Could not fetch the Purananuru Wikisource pages: "
            f"{response.stderr.strip() or response.returncode}"
        )
    payload = json.loads(response.stdout)
    pages = payload.get("query", {}).get("pages")
    if not isinstance(pages, list):
        raise ValueError("Wikisource returned no Purananuru page list.")
    return pages


def _clean_wikitext(value: str) -> str:
    value = re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL)
    value = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", value)
    value = re.sub(r"\{\{[^{}]*\}\}", "", value)
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"</(?:p|div|poem)\s*>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = re.sub(r"'{2,5}", "", value)
    value = html.unescape(value)
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def _metadata(segment: str, label: str) -> str | None:
    label_pattern = (
        r"பாடப்பட்ட(?:ோன்|ோர்)" if label == "பாடப்பட்டோன்" else re.escape(label)
    )
    for line in _clean_wikitext(segment).splitlines():
        match = re.search(rf"{label_pattern}\s*[:：;]\s*(.+)", line)
        if match is None:
            continue
        value = re.split(
            r"\s+(?:பாடியவர்|பாடியோர்|பாடப்பட்டோன்|திணை|துறை|குறிப்பு|சிறப்பு)"
            r"\s*[:：;]",
            match.group(1),
            maxsplit=1,
        )[0]
        value = re.sub(r"^=+|=+$", "", value).strip()
        value = value.rstrip(".。;； ")
        return value or None
    return None


def _verse_lines(
    segment: str,
    allow_unmarked: bool = False,
    first_paragraph_only: bool = False,
) -> list[str]:
    numbered_lines = []
    if LINE_NUMBER_MARKER.search(segment):
        for line in segment.splitlines():
            match = LINE_NUMBERED_VERSE.fullmatch(line)
            if match is None:
                continue
            text = _clean_wikitext(match.group(1))
            if (
                not text
                or METADATA_LABEL.match(text)
                or re.fullmatch(r"\(.*\)", text)
                or any(marker in text for marker in ("பாடியது", "பாடபேதம்", "குறிப்பு"))
            ):
                continue
            numbered_lines.append(text)
    if len(numbered_lines) >= 2:
        return _sanitize_verse_lines(numbered_lines)

    cleaned_segment = _clean_wikitext(segment)
    stanza = STANZA.search(cleaned_segment)
    if stanza is not None:
        metadata_matches = list(METADATA_LABEL.finditer(cleaned_segment))
        if metadata_matches and metadata_matches[-1].start() < stanza.start():
            prefix_text = cleaned_segment[metadata_matches[-1].end() : stanza.start()]
            prefix_lines = prefix_text.splitlines()[1:]
            verse_prefix = []
            for line in prefix_lines:
                visible_line = line.strip().lstrip(":").strip()
                if (
                    not visible_line
                    or visible_line.startswith((";", "#", "=", "-"))
                    or METADATA_LABEL.match(visible_line)
                    or re.fullmatch(r"\(.*\)", visible_line)
                    or any(
                        marker in visible_line
                        for marker in ("குறிப்பு", "பாடபேதம்", "பாடியது")
                    )
                ):
                    continue
                verse_prefix.append(visible_line)
            if len(verse_prefix) >= 3:
                return _sanitize_verse_lines(verse_prefix)
        stanza_lines = stanza.group(1).splitlines()
        if stanza_lines:
            return _sanitize_verse_lines(stanza_lines)

    blocks = [
        cleaned
        for block in re.split(r"\n\s*\n", segment)
        if (cleaned := _clean_wikitext(block))
    ]
    metadata_blocks = [
        block_index
        for block_index, block in enumerate(blocks)
        if any(METADATA_LABEL.match(line.strip()) for line in block.splitlines())
    ]
    if metadata_blocks:
        metadata_index = metadata_blocks[-1]
        verse_blocks = blocks[metadata_index + 1 :]
        if not verse_blocks:
            lines = blocks[metadata_index].splitlines()
            block_metadata_indexes = [
                line_index
                for line_index, line in enumerate(lines)
                if METADATA_LABEL.match(line.strip())
            ]
            verse = "\n".join(lines[block_metadata_indexes[-1] + 1 :])
        else:
            selected_blocks = []
            for block in verse_blocks:
                normalized_block = block.strip()
                is_annotation = normalized_block.startswith((";", "#", "====="))
                is_separator = re.fullmatch(r"[. …]+", normalized_block) is not None
                if (
                    is_annotation
                    or is_separator
                    or "குறிப்பு" in normalized_block
                    or "பாடபேதம்" in normalized_block
                ):
                    if selected_blocks:
                        break
                    continue
                if re.fullmatch(r"\(.*\)", normalized_block):
                    if selected_blocks:
                        break
                    continue
                selected_blocks.append(block)
                if first_paragraph_only:
                    break
            verse = "\n".join(selected_blocks)
    else:
        numbered_lines = []
        for line in segment.splitlines():
            match = LINE_NUMBERED_VERSE.fullmatch(line)
            if match is None:
                continue
            text = _clean_wikitext(match.group(1))
            if text and not re.fullmatch(r"\(.*\)", text):
                numbered_lines.append(text)
        if len(numbered_lines) >= 2:
            return _sanitize_verse_lines(numbered_lines)

        stanza = STANZA.search(segment)
        if stanza is not None:
            verse = stanza.group(1)
        elif allow_unmarked:
            verse = blocks[0] if first_paragraph_only and blocks else "\n".join(blocks)
        else:
            return []
    return _sanitize_verse_lines(_clean_wikitext(verse).splitlines())


def _sanitize_verse_lines(lines: list[str]) -> list[str]:
    sanitized = []
    for line in lines:
        text = line.strip().lstrip(":").strip()
        if (
            not text
            or text.startswith((";", "#"))
            or text.startswith("-")
            or METADATA_LABEL.match(text)
            or any(
                marker in text
                for marker in ("பாடியது", "பாடபேதம்", "குறிப்பு", "துணை:")
            )
            or ("பாடினோர்" in text and "அழிந்தது" in text)
        ):
            continue
        text = re.sub(r"\s*\(\d+\)\s*$", "", text).strip()
        if text:
            sanitized.append(text)
    return sanitized


def _record(
    *,
    poem_id: int,
    title: str | None,
    body: str,
    source_page: str,
    revision_id: int,
    allow_unmarked: bool = False,
    first_paragraph_only: bool = False,
) -> dict[str, Any] | None:
    lines = _verse_lines(
        body,
        allow_unmarked=allow_unmarked,
        first_paragraph_only=first_paragraph_only,
    )
    if len(lines) < 3:
        return None
    source_url = (
        f"{WIKISOURCE_ROOT}/wiki/{quote(source_page.replace(' ', '_'))}"
        f"?oldid={revision_id}"
    )
    return {
        "id": poem_id,
        "title": title,
        "poet": _metadata(body, "பாடியவர்") or _metadata(body, "பாடியோர்"),
        "dedicatee": _metadata(body, "பாடப்பட்டோன்"),
        "thinai": _metadata(body, "திணை"),
        "thurai": _metadata(body, "துறை"),
        "lines": lines,
        "source_url": source_url,
        "source_page": source_page,
        "source_revision_id": revision_id,
        "source_license": LICENSE,
        "source_license_url": LICENSE_URL,
        "scan_source_url": CICT_SCAN_URL,
    }


def _parse_page(page: dict[str, Any]) -> list[dict[str, Any]]:
    revisions = page.get("revisions")
    if not isinstance(revisions, list) or not revisions:
        raise ValueError(f"Missing Wikisource page: {page.get('title', '<unknown>')}.")
    revision = revisions[0]
    content = revision.get("slots", {}).get("main", {}).get("content")
    if not isinstance(content, str):
        raise ValueError(f"Missing source text in Wikisource page {page['title']}.")
    revision_id = revision.get("revid")
    if not isinstance(revision_id, int):
        raise ValueError(f"Missing revision ID for Wikisource page {page['title']}.")

    page_title = page["title"]
    page_range = re.search(r"(\d+)-(\d+)$", page_title)
    if page_range is None:
        raise ValueError(f"Missing poem range in Wikisource page {page_title}.")
    first_poem, last_poem = map(int, page_range.groups())

    records: list[dict[str, Any]] = []

    def keep_in_range(record: dict[str, Any] | None) -> None:
        if record is None:
            return
        if first_poem <= record["id"] <= last_poem:
            records.append(record)

    wrapped_poems = list(POEM_TAG.finditer(content))
    if wrapped_poems:
        previous_end = 0
        for poem in wrapped_poems:
            prefix = content[previous_end : poem.start()]
            previous_end = poem.end()
            numbered_titles = [
                match
                for line in prefix.splitlines()
                if (match := NUMBERED_TITLE_LINE.fullmatch(line.strip()))
            ]
            trailing_number_titles = [
                match
                for line in prefix.splitlines()
                if (match := TRAILING_NUMBER_TITLE_LINE.fullmatch(line.strip()))
            ]
            ids = [
                int(match.group(1))
                for line in prefix.splitlines()
                if (match := POEM_ID_LINE.fullmatch(line))
            ]
            if numbered_titles:
                ids.append(int(numbered_titles[-1].group(1)))
            if trailing_number_titles:
                ids.append(int(trailing_number_titles[-1].group(2)))
            if not ids:
                raise ValueError(f"Could not identify a poem number on {page_title}.")
            titles = [
                match.group(1).strip()
                for line in prefix.splitlines()
                if (match := TITLE_LINE.fullmatch(line.strip()))
                and not re.search(r"பாடல்\s*[:：]?\s*\d+", match.group(1))
            ]
            record = _record(
                poem_id=ids[-1],
                title=(
                    numbered_titles[-1].group(2).strip()
                    if numbered_titles
                    else (
                        trailing_number_titles[-1].group(1).strip()
                        if trailing_number_titles
                        else titles[-1] if titles else None
                    )
                ),
                body=poem.group(1),
                source_page=page_title,
                revision_id=revision_id,
                allow_unmarked=True,
                first_paragraph_only=True,
            )
            keep_in_range(record)
        return records

    headings = list(POEM_HEADING.finditer(content))
    for index, heading in enumerate(headings):
        end = headings[index + 1].start() if index + 1 < len(headings) else len(content)
        segment = content[heading.end() : end]
        title = re.search(r"\(([^()]*)\)", heading.group(2))
        record = _record(
            poem_id=int(heading.group(1)),
            title=title.group(1).strip() if title else None,
            body=segment,
            source_page=page_title,
            revision_id=revision_id,
            allow_unmarked=True,
        )
        keep_in_range(record)
    return records


def build_corpus(pages: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    source_pages = _fetch_wikisource_pages() if pages is None else pages
    records = [
        record
        for page in source_pages
        for record in _parse_page(page)
    ]
    ids = [record["id"] for record in records]
    duplicates = sorted({poem_id for poem_id in ids if ids.count(poem_id) > 1})
    missing = sorted(EXPECTED_POEM_IDS - set(ids))
    unexpected = sorted(set(ids) - EXPECTED_POEM_IDS)
    if duplicates or missing or unexpected:
        raise ValueError(
            "Purananuru import failed integrity checks: "
            f"duplicates={duplicates}, missing={missing}, unexpected={unexpected}."
        )

    records.sort(key=lambda record: record["id"])
    PURANANURU_CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PURANANURU_CORPUS_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return records


if __name__ == "__main__":
    corpus = build_corpus()
    print(
        f"Built {len(corpus)} Purananuru poems at "
        f"{PURANANURU_CORPUS_PATH}."
    )
