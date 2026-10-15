"""Central configuration for corpus construction, matching, and the API."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env", override=True)

DATA_RAW_DIR = Path(os.getenv("DATA_RAW_DIR", ROOT_DIR / "data" / "raw"))
DATA_CLEAN_DIR = Path(os.getenv("DATA_CLEAN_DIR", ROOT_DIR / "data" / "clean"))
EVAL_DIR = Path(os.getenv("EVAL_DIR", ROOT_DIR / "eval"))
CORPUS_PATH = Path(os.getenv("CORPUS_PATH", DATA_CLEAN_DIR / "kural.json"))
EVAL_RESULTS_PATH = Path(os.getenv("EVAL_RESULTS_PATH", EVAL_DIR / "results.json"))
EVAL_SET_PATH = Path(os.getenv("EVAL_SET_PATH", EVAL_DIR / "eval_set.json"))

SOURCE_A_VERSES_URL = os.getenv(
    "SOURCE_A_VERSES_URL",
    "https://raw.githubusercontent.com/tk120404/thirukkural/master/thirukkural.json",
)
SOURCE_A_DETAIL_URL = os.getenv(
    "SOURCE_A_DETAIL_URL",
    "https://raw.githubusercontent.com/tk120404/thirukkural/master/detail.json",
)
SOURCE_B_PRIMARY_URL = os.getenv(
    "SOURCE_B_PRIMARY_URL", "https://api-thirukkural.vercel.app/api?num={id}"
)
SOURCE_B_FALLBACK_URL = os.getenv(
    "SOURCE_B_FALLBACK_URL", "https://thirukkural.senkanthal.org/kural"
)
SOURCE_TIMEOUT_SECONDS = float(os.getenv("SOURCE_TIMEOUT_SECONDS", "20"))

NEAR_THRESHOLD = int(os.getenv("NEAR_THRESHOLD", "80"))
CHARACTER_WEIGHT = float(os.getenv("CHARACTER_WEIGHT", "0.7"))
WORD_OVERLAP_WEIGHT = float(os.getenv("WORD_OVERLAP_WEIGHT", "0.3"))
MIN_STANDALONE_TAMIL_WORDS = int(os.getenv("MIN_STANDALONE_TAMIL_WORDS", "4"))
MAX_VERIFY_TEXT_LENGTH = int(os.getenv("MAX_VERIFY_TEXT_LENGTH", "5000"))
MAX_GUARD_TEXT_LENGTH = int(os.getenv("MAX_GUARD_TEXT_LENGTH", "20000"))
CORS_ALLOW_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "*")

GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("EDUCATION_LLM_API_KEY")
    or ""
).strip().strip('"').strip("'")
GEMINI_MODEL = (
    os.getenv("GEMINI_MODEL")
    or "gemini-3.5-flash-lite"
).strip().strip('"').strip("'")
GEMINI_API_TIMEOUT_SECONDS = float(
    os.getenv(
        "GEMINI_API_TIMEOUT_SECONDS",
        os.getenv("EDUCATION_LLM_TIMEOUT_SECONDS", "45"),
    )
)
