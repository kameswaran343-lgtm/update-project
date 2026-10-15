# KuralGuard

KuralGuard checks Tamil quotations against a fetched local Tirukkural corpus and abstains when it cannot confirm a match.

## Run & Operate

- `./run.sh` — build the local corpus and evaluation report, then start FastAPI and the web app
- `python3.11 scripts/build_corpus.py` — fetch and validate source data
- `python3.11 eval/run_eval.py` — regenerate the deterministic evaluation set and metrics
- `python3.11 -m pytest -q` — run backend tests
- `pnpm run typecheck` — full typecheck across all packages
- `PORT=5173 BASE_PATH=/ pnpm run build` — typecheck + build all packages (the Vite packages require these values)
- Required runtime: Python 3.11, Node.js, and pnpm
- Python dependencies: `requirements.txt`
- No database or API key is required

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: FastAPI + Pydantic
- Corpus: immutable raw source snapshots, normalized JSON runtime corpus
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Web: React + Vite, Recharts, Noto Sans Tamil

## Where things live

- `config.py` — environment-backed paths, public sources, CORS, and matching thresholds
- `scripts/build_corpus.py` — immutable-source downloader, cross-checker, and corpus validator
- `engine/` — normalization and local-only exact/fuzzy matching
- `guard/` — FastAPI routes and quote extraction/annotation
- `eval/` — seed-42 generated cases and threshold-sweep report
- `data/raw/` — fetched upstream snapshots; do not edit them
- `data/clean/kural.json` — normalized runtime source of truth
- `lib/api-spec/openapi.yaml` — API contract and generated TypeScript hooks
- `artifacts/meikural/` — registered React/Vite interface

## Architecture decisions

- `/verify` has no network or LLM dependency; the local corpus is the only authority.
- A missing quote is an abstention, never a claim that it is fake.
- Two-source disagreements keep source A and are marked for human review.
- The requested API was unavailable at build time; the builder falls back to the separately hosted Senkanthal API.

## Product

- Verify one Tamil quote and optional attribution.
- Guard a pasted chatbot answer by extracting and checking candidate quotations.
- Inspect generated evaluation metrics and threshold trade-offs.

## User preferences

- Never invent or manually edit Tirukkural text; use fetched source files only.
- Use “not found / cannot confirm” and advise consultation with a Tamil scholar; never say a quote is fake.

## Gotchas

- Run `scripts/build_corpus.py` before starting the API if the cleaned corpus is absent or source data changes.
- `data/raw/` is immutable; the builder reuses existing snapshots instead of overwriting them.

## Pointers

- See `README.md` for source details, licensing, threshold rationale, setup, and limitations.
