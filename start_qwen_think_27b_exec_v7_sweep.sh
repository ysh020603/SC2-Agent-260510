#!/usr/bin/env bash
# 6 strategies vs 3 races @ KairosJunctionLE (default map)
# naming/ordering: Qwen3-4b_think or Qwen3-14b_think (thinking)
# executor: Qwen35-27b (no thinking)
# difficulties: easy, medium, mediumhard | 3 repeats per combo
#
# Usage:
#   bash start_qwen_think_27b_exec_v7_sweep.sh 4b
#   bash start_qwen_think_27b_exec_v7_sweep.sh 14b
#   bash start_qwen_think_27b_exec_v7_sweep.sh both
#
# Resume:
#   START_INDEX=42 bash start_qwen_think_27b_exec_v7_sweep.sh 4b

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

STRATEGIES="${STRATEGIES:-bio,safe_tvt_raven,three_rax_stim,two_base_tanks,tank_thor_mech,battle_cruisers}"
DIFFICULTIES="${DIFFICULTIES:-easy,medium,mediumhard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-random}"
MAPS="${MAPS:-KairosJunctionLE}"
REPEATS="${REPEATS:-3}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
CONCURRENCY="${CONCURRENCY:-6}"
EXECUTOR_MODEL="${EXECUTOR_MODEL:-Qwen35-27b}"
# 6 strategies x 3 races x 3 difficulties x 3 repeats = 162
TOTAL_JOBS=162

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

_start_sweep() {
  local which="$1"
  local session batch think_model

  case "$which" in
    4b|qwen3-4b)
      session="${TMUX_SESSION_4B:-qwen4b_think_27b_exec_v7_sweep}"
      batch="${BATCH_NAME_4B:-qwen4b_think_27b_exec_v7_r3}"
      think_model="Qwen3-4b_think"
      ;;
    14b|qwen3-14b)
      session="${TMUX_SESSION_14B:-qwen14b_think_27b_exec_v7_sweep}"
      batch="${BATCH_NAME_14B:-qwen14b_think_27b_exec_v7_r3}"
      think_model="Qwen3-14b_think"
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
CONCURRENCY=$(printf '%q' "$CONCURRENCY") \
REPEATS=$(printf '%q' "$REPEATS") \
GAME_TIME_LIMIT=$(printf '%q' "$GAME_TIME_LIMIT") \
START_INDEX=$(printf '%q' "${START_INDEX:-0}") \
NAMING_MODEL=$(printf '%q' "$think_model") \
ORDERING_MODEL=$(printf '%q' "$think_model") \
EXECUTOR_MODEL=$(printf '%q' "$EXECUTOR_MODEL") \
STRATEGIES=$(printf '%q' "$STRATEGIES") \
DIFFICULTIES=$(printf '%q' "$DIFFICULTIES") \
ENEMY_RACES=$(printf '%q' "$ENEMY_RACES") \
ENEMY_BUILD=$(printf '%q' "$ENEMY_BUILD") \
MAPS=$(printf '%q' "$MAPS") \
bash tools/run_strategy_sweep_tmux.sh"

  echo "=================================================="
  echo " Started           : ${think_model} + ${EXECUTOR_MODEL}"
  echo " Tmux session      : $session"
  echo " Batch folder      : game_records/${batch}/"
  echo " Map               : ${MAPS}"
  echo " Naming/Ordering   : ${think_model} (thinking)"
  echo " Executor          : ${EXECUTOR_MODEL} (no thinking)"
  echo " Strategies        : ${STRATEGIES}"
  echo " Opponent          : ${ENEMY_RACES} | build=${ENEMY_BUILD}"
  echo " Difficulties      : ${DIFFICULTIES}"
  echo " Repeats           : ${REPEATS} per combo"
  echo " Concurrency       : ${CONCURRENCY}"
  echo " Total jobs        : ${TOTAL_JOBS}"
  echo " Attach            : tmux attach -t ${session}"
  echo " Logs              : game_records/${batch}_stdout.log"
  echo "=================================================="
}

TARGET="${1:-both}"
case "$TARGET" in
  both)
    _start_sweep 4b
    echo ""
    _start_sweep 14b
    ;;
  4b|qwen3-4b|14b|qwen3-14b)
    _start_sweep "$TARGET"
    ;;
  *)
    echo "Usage: $0 [both|4b|14b]" >&2
    exit 1
    ;;
esac
