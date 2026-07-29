#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export SC2PATH="${SC2PATH:-/data2/SC2/StarCraftII/}"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1

BATCH_NAME="${BATCH_NAME:-kimi_nothink_summary_queue}"
DECISION_MODEL="${DECISION_MODEL:-Kimi-k2.5}"
DECISION_INTERVAL="${DECISION_INTERVAL:-60}"
CONCURRENCY="${CONCURRENCY:-3}"
REPEATS="${REPEATS:-2}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
START_INDEX="${START_INDEX:-0}"

python tools/run_kimi_nothink_strategy_sweep.py \
  --batch-name "$BATCH_NAME" \
  --decision-model "$DECISION_MODEL" \
  --decision-interval "$DECISION_INTERVAL" \
  --concurrency "$CONCURRENCY" \
  --repeats "$REPEATS" \
  --game-time-limit "$GAME_TIME_LIMIT" \
  --start-index "$START_INDEX"
