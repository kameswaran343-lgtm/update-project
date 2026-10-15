#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

python3.11 scripts/build_corpus.py
python3.11 eval/run_eval.py

cleanup() {
  if [[ -n "${API_PID:-}" ]]; then kill "$API_PID" 2>/dev/null || true; fi
  if [[ -n "${WEB_PID:-}" ]]; then kill "$WEB_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

python3.11 -m uvicorn guard.api:app --host 0.0.0.0 --port "$API_PORT" &
API_PID=$!

KURALGUARD_LOCAL_STACK=1 \
KURALGUARD_API_PORT="$API_PORT" \
PORT="$WEB_PORT" \
BASE_PATH="/" \
pnpm --filter @workspace/kuralguard run dev &
WEB_PID=$!

printf 'KuralGuard API: http://127.0.0.1:%s/api/health\n' "$API_PORT"
printf 'KuralGuard web: http://127.0.0.1:%s/\n' "$WEB_PORT"
wait -n "$API_PID" "$WEB_PID"
