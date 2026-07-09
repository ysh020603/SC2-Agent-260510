#!/usr/bin/env bash
# Same as Qwen35 全模块 bio+bc sweep, for Qwen3 small/mid models (no thinking)
#
# Usage:
#   bash tools/start_qwen3_bio_bc_3race_macro_sweep.sh qwen3-4b
#   bash tools/start_qwen3_bio_bc_3race_macro_sweep.sh qwen3-14b
#   bash tools/start_qwen3_bio_bc_3race_macro_sweep.sh 4b14b   # both 4B+14B, concurrency=10

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

STRATEGIES="${STRATEGIES:-bio,battle_cruisers}"
DIFFICULTIES="${DIFFICULTIES:-veryeasy,medium,hard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"
REPEATS="${REPEATS:-5}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
TOTAL_JOBS=90

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

_start_sweep() {
  local which="$1"
  local session batch model concurrency

  case "$which" in
    qwen3-4b|4b)
      session="${TMUX_SESSION_4B:-qwen3_4b_bio_bc_3race_sweep}"
      batch="${BATCH_NAME_4B:-qwen3_4b_bio_bc_3race_macro_r5}"
      model="Qwen3-4b"
      concurrency="${CONCURRENCY_4B:-10}"
      ;;
    qwen3-14b|14b)
      session="${TMUX_SESSION_14B:-qwen3_14b_bio_bc_3race_sweep}"
      batch="${BATCH_NAME_14B:-qwen3_14b_bio_bc_3race_macro_r5}"
      model="Qwen3-14b"
      concurrency="${CONCURRENCY_14B:-10}"
      ;;
    qwen3-8b|8b)
      session="${TMUX_SESSION_8B:-qwen3_8b_bio_bc_3race_sweep}"
      batch="${BATCH_NAME_8B:-qwen3_8b_bio_bc_3race_macro_r5}"
      model="Qwen3-8b"
      concurrency="${CONCURRENCY_8B:-5}"
      ;;
    qwen3-1.7b|1.7b|17b)
      session="${TMUX_SESSION_17B:-qwen3_17b_bio_bc_3race_sweep}"
      batch="${BATCH_NAME_17B:-qwen3_17b_bio_bc_3race_macro_r5}"
      model="Qwen3-1.7b"
      concurrency="${CONCURRENCY_17B:-5}"
      ;;
    qwen3-32b|32b)
      session="${TMUX_SESSION_32B:-qwen3_32b_bio_bc_3race_sweep}"
      batch="${BATCH_NAME_32B:-qwen3_32b_bio_bc_3race_macro_r5}"
      model="Qwen3-32b"
      concurrency="${CONCURRENCY_32B:-5}"
      ;;
    *)
      echo "Unknown target: $which" >&2
      return 1
      ;;
  esac

  if tmux has-session -t "$session" 2>/dev/null; then
    echo "Killing existing tmux session: $session"
    tmux kill-session -t "$session" 2>/dev/null || true
    sleep 1
  fi

  pkill -f "run_kimi_nothink_strategy_sweep.py --batch-name ${batch}" 2>/dev/null || true
  pkill -f "run_experiment.py.*--batch-name ${batch}" 2>/dev/null || true
  sleep 1

  tmux new-session -d -s "$session" -n sweep \
    "cd $(printf '%q' "$ROOT") && \
BATCH_NAME=$(printf '%q' "$batch") \
CONCURRENCY=$(printf '%q' "$concurrency") \
REPEATS=$(printf '%q' "$REPEATS") \
GAME_TIME_LIMIT=$(printf '%q' "$GAME_TIME_LIMIT") \
START_INDEX=$(printf '%q' "${START_INDEX:-0}") \
NAMING_MODEL=$(printf '%q' "$model") \
ORDERING_MODEL=$(printf '%q' "$model") \
EXECUTOR_MODEL=$(printf '%q' "$model") \
STRATEGIES=$(printf '%q' "$STRATEGIES") \
DIFFICULTIES=$(printf '%q' "$DIFFICULTIES") \
ENEMY_RACES=$(printf '%q' "$ENEMY_RACES") \
ENEMY_BUILD=$(printf '%q' "$ENEMY_BUILD") \
MAPS=$(printf '%q' "$MAPS") \
bash $(printf \'%q\' "$SCRIPT_DIR/run_strategy_sweep_tmux.sh")"
  echo "=================================================="
  echo " Started : ${model}"
  echo " Tmux    : $session"
  echo " Batch   : game_records/${batch}/"
  echo " Model   : ${model} (naming/ordering/executor, no thinking)"
  echo " Jobs    : ${TOTAL_JOBS} | Concur: ${concurrency}"
  echo " Attach  : tmux attach -t ${session}"
  echo "=================================================="
}

TARGET="${1:-both}"
case "$TARGET" in
  both)
    _start_sweep qwen3-8b
    echo ""
    _start_sweep qwen3-1.7b
    ;;
  4b14b)
    _start_sweep qwen3-4b
    echo ""
    _start_sweep qwen3-14b
    ;;
  qwen3-4b|4b|qwen3-14b|14b|qwen3-8b|8b|qwen3-1.7b|1.7b|17b|qwen3-32b|32b)
    _start_sweep "$TARGET"
    ;;
  *)
    echo "Usage: $0 [both|4b14b|qwen3-4b|qwen3-14b|qwen3-8b|qwen3-1.7b|qwen3-32b]" >&2
    exit 1
    ;;
esac
