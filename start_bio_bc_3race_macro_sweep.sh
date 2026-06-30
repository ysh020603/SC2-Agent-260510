#!/usr/bin/env bash
# bio + battle_cruisers vs 3 races (macro) @ KairosJunctionLE
# difficulties: veryeasy, medium, hard | 5 repeats per combo
# Models: Qwen35-27b only (Kimi replaced by ds_flash_qwen_exec batch)
#
# Usage:
#   bash start_bio_bc_3race_macro_sweep.sh qwen
# DS flash + Qwen executor: start_ds_flash_qwen_exec_bio_bc_sweep.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

STRATEGIES="${STRATEGIES:-bio,battle_cruisers}"
DIFFICULTIES="${DIFFICULTIES:-veryeasy,medium,hard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"
REPEATS="${REPEATS:-5}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"

# 2 strategies x 3 races x 3 difficulties x 5 repeats = 90 jobs per model
TOTAL_JOBS=90

_start_sweep() {
  local which="$1"
  local session batch model concurrency

  case "$which" in
    qwen)
      session="${TMUX_SESSION_QWEN:-qwen35_bio_bc_3race_sweep}"
      batch="${BATCH_NAME_QWEN:-qwen35_bio_bc_3race_macro_r5}"
      model="Qwen35-27b"
      concurrency="${CONCURRENCY_QWEN:-5}"
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
bash tools/run_strategy_sweep_tmux.sh"

  echo "=================================================="
  echo " Started : $which"
  echo " Tmux    : $session"
  echo " Batch   : game_records/${batch}/"
  echo " Model   : ${model} (no thinking)"
  echo " Jobs    : ${TOTAL_JOBS} (2 strategies x 3 races x 3 diffs x 5 reps)"
  echo " Concur  : ${concurrency}"
  echo " Attach  : tmux attach -t ${session}"
  echo " Logs    : game_records/${batch}_stdout.log"
  echo "=================================================="
}

TARGET="${1:-qwen}"
case "$TARGET" in
  qwen)
    _start_sweep qwen
    ;;
  *)
    echo "Usage: $0 [qwen]" >&2
    exit 1
    ;;
esac
