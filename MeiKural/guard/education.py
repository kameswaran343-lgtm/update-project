"""On-demand, cached simple explanations for verified Tirukkural entries."""

from __future__ import annotations

from functools import lru_cache
import logging
from typing import Literal
from urllib.parse import quote

import httpx

from config import (
    GEMINI_API_KEY,
    GEMINI_API_TIMEOUT_SECONDS,
    GEMINI_MODEL,
)

logger = logging.getLogger(__name__)

ExplanationLanguage = Literal["ta", "en"]
GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

FALLBACK_MODELS = (
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
)


class ExplanationUnavailableError(Exception):
    """The configured Gemini API could not provide a usable explanation."""


@lru_cache(maxsize=256)
def generate_simple_explanation(
    kural_id: int,
    language: ExplanationLanguage,
    line1: str,
    line2: str,
    meaning_en: str,
) -> str:
    api_key = (GEMINI_API_KEY or "").strip().strip('"').strip("'")
    if not api_key:
        raise ExplanationUnavailableError(
            "Simple explanations are not configured. Add GEMINI_API_KEY "
            "to the server environment."
        )
    configured_model = (GEMINI_MODEL or "").strip().strip('"').strip("'")
    if not configured_model:
        raise ExplanationUnavailableError(
            "Simple explanations are not configured. Set GEMINI_MODEL "
            "in the server environment."
        )

    if language == "ta":
        instruction = (
            "Explain this Tirukkural in clear, simple modern Tamil. Keep the "
            "original couplet and supplied traditional meaning unchanged. "
            "Explain only the idea supported by them; do not invent historical "
            "claims. Use a short everyday example only when it genuinely helps. "
            "Return only the explanation, with an optional example clearly "
            "labelled in Tamil."
        )
    else:
        instruction = (
            "Explain this Tirukkural in clear, simple English. Keep the original "
            "couplet and supplied traditional meaning unchanged. Explain only "
            "the idea supported by them; do not invent historical claims. Use "
            "a short everyday example only when it genuinely helps. Return only "
            "the explanation, with an optional example clearly labelled."
        )
    prompt = (
        f"Kural number: {kural_id}\n"
        f"Original Tamil couplet, line 1: {line1}\n"
        f"Original Tamil couplet, line 2: {line2}\n"
        "Source English meaning (omitted if unavailable or flagged for review): "
        f"{meaning_en or 'Not available.'}\n"
    )

    models_to_try = [configured_model]
    for fallback in FALLBACK_MODELS:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    last_error: Exception | None = None
    explanation: str | None = None

    for model_name in models_to_try:
        try:
            model = quote(model_name, safe="-._")
            response = httpx.post(
                f"{GEMINI_API_BASE_URL}/models/{model}:generateContent",
                headers={"x-goog-api-key": api_key},
                json={
                    "systemInstruction": {"parts": [{"text": instruction}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.3},
                },
                timeout=GEMINI_API_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            candidates = payload.get("candidates") or []
            if not candidates:
                continue
            parts = candidates[0].get("content", {}).get("parts", [])
            extracted = "".join(
                part["text"]
                for part in parts
                if (
                    isinstance(part, dict)
                    and part.get("thought") is not True
                    and isinstance(part.get("text"), str)
                )
            ).strip()
            if extracted:
                explanation = extracted
                break
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status = getattr(exc.response, "status_code", "unknown")
            logger.warning(
                "Gemini model %s failed with status %s: %s",
                model_name,
                status,
                str(exc),
            )
            if isinstance(status, int) and status in (404, 503, 429):
                continue
            break
        except (httpx.RequestError, ValueError, KeyError, IndexError, TypeError) as exc:
            last_error = exc
            logger.warning("Gemini model %s request failed: %s", model_name, exc)
            continue

    if explanation is None:
        if isinstance(last_error, httpx.HTTPStatusError):
            raise ExplanationUnavailableError(
                "The explanation service returned an error. Please try again later."
            ) from last_error
        raise ExplanationUnavailableError(
            "The explanation service is unavailable or returned an invalid response."
        ) from last_error

    return explanation
