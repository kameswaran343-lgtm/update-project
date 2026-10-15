"""Extract quote candidates and Kural citations from pasted answers."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from config import MIN_STANDALONE_TAMIL_WORDS

QUOTED_TEXT = re.compile(
    r"“(?P<curly_double>[^”]+)”|‘(?P<curly_single>[^’]+)’|"
    r'"(?P<double>[^"]+)"|\'(?P<single>[^\'\n]+)\''
)
KURAL_CITATION = re.compile(
    r"(?:திருக்குறள்|குறள்|thirukkural|kural)\s*"
    r"(?:எண்|no\.?|#|:)?\s*(?:எண்\s*)?(\d{1,4})",
    re.IGNORECASE,
)

def _has_tamil_letter(token: str) -> bool:
    return any(
        0x0B80 <= ord(character) <= 0x0BFF
        and unicodedata.category(character).startswith("L")
        for character in token
    )


@dataclass(frozen=True)
class QuoteCandidate:
    text: str
    start: int
    end: int
    claimed_id: int | None


def _claim_near(
    start: int, end: int, citations: list[tuple[int, int, int]]
) -> int | None:
    nearby = [
        (claim_start, claim_end, claim_id)
        for claim_start, claim_end, claim_id in citations
        if claim_start <= end + 140 and claim_end >= start - 140
    ]
    if not nearby:
        return None
    return min(
        nearby,
        key=lambda item: min(abs(item[0] - end), abs(start - item[1])),
    )[2]


def extract_candidates(answer: str) -> list[QuoteCandidate]:
    """Return distinct quoted spans and standalone Tamil lines with 4+ words."""
    citations = [
        (match.start(), match.end(), int(match.group(1)))
        for match in KURAL_CITATION.finditer(answer)
        if 1 <= int(match.group(1)) <= 1330
    ]
    candidates: list[QuoteCandidate] = []
    occupied: list[tuple[int, int]] = []

    for match in QUOTED_TEXT.finditer(answer):
        text = next((value for value in match.groupdict().values() if value), "")
        text = text.strip()
        if not text:
            continue
        candidates.append(
            QuoteCandidate(
                text=text,
                start=match.start(),
                end=match.end(),
                claimed_id=_claim_near(match.start(), match.end(), citations),
            )
        )
        occupied.append((match.start(), match.end()))

    offset = 0
    for line in answer.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        start, end = offset, offset + len(content)
        offset += len(line)
        if not content.strip():
            continue
        if any(start < quoted_end and end > quoted_start for quoted_start, quoted_end in occupied):
            continue
        tamil_words = [word for word in content.split() if _has_tamil_letter(word)]
        if len(tamil_words) >= MIN_STANDALONE_TAMIL_WORDS:
            candidates.append(
                QuoteCandidate(
                    text=content.strip(),
                    start=start,
                    end=end,
                    claimed_id=_claim_near(start, end, citations),
                )
            )
    candidates.sort(key=lambda candidate: candidate.start)
    deduplicated: list[QuoteCandidate] = []
    seen: set[tuple[int, int, str]] = set()
    for candidate in candidates:
        key = (candidate.start, candidate.end, candidate.text)
        if key not in seen:
            seen.add(key)
            deduplicated.append(candidate)
    if len(deduplicated) == 1 and len(citations) == 1:
        candidate = deduplicated[0]
        if candidate.claimed_id is None:
            deduplicated[0] = QuoteCandidate(
                text=candidate.text,
                start=candidate.start,
                end=candidate.end,
                claimed_id=citations[0][2],
            )
    return deduplicated
