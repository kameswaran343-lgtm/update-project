"""Unicode normalization helpers for Tamil quotation matching."""

from __future__ import annotations

import unicodedata

ZERO_WIDTH_CHARACTERS = "\u200b\u200c\u200d"
TAMIL_BLOCK_START = 0x0B80
TAMIL_BLOCK_END = 0x0BFF


def normalize(text: str) -> str:
    """Keep Tamil letters/marks, remove punctuation and digits, and fold spaces."""
    nfc_text = unicodedata.normalize("NFC", text).translate(
        {ord(character): None for character in ZERO_WIDTH_CHARACTERS}
    )
    kept: list[str] = []
    for character in nfc_text:
        if character.isspace():
            kept.append(" ")
            continue
        codepoint = ord(character)
        category = unicodedata.category(character)
        if (
            TAMIL_BLOCK_START <= codepoint <= TAMIL_BLOCK_END
            and category[0] in {"L", "M"}
        ):
            kept.append(character)
    return " ".join("".join(kept).split())


def normalize_compact(text: str) -> str:
    """Normalized text with all whitespace removed for exact quote matching."""
    return normalize(text).replace(" ", "")
