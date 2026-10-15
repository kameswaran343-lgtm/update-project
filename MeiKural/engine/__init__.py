"""Local-corpus normalization and deterministic matching."""

from .matcher import Matcher, Verification, get_matcher, verify
from .normalize import normalize, normalize_compact

__all__ = [
    "Matcher",
    "Verification",
    "get_matcher",
    "normalize",
    "normalize_compact",
    "verify",
]
