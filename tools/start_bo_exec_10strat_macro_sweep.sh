#!/usr/bin/env bash
# BO-list mode: 10 Terran strategies vs 3 races (macro) @ KairosJunctionLE
# Compare executor models only (Naming/Ordering bypassed via --bo-list)
# Protocol aligned with game_records/qwen17b_naming_27b_exec_10strat_macro_experiment.md
#
# Usage:
#   bash tools/start_bo_exec_10strat_macro_sweep.sh grpo      # GRPO executor (thinking)
#   bash tools/start_bo_exec_10strat_macro_sweep.sh 17b_think # Qwen3-1.7b_think executor
#   bash tools/start_bo_exec_10strat_macro_sweep.sh 27b       # Qwen35-27b executor (no thinking)
#   bash tools/start_bo_exec_10strat_macro_sweep.sh all       # launch all three (separate tmux)
# Resume: START_INDEX=N bash tools/start_bo_exec_10strat_macro_sweep.sh grpo

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

STRATEGIES="${STRATEGIES:-bio,safe_tvt_raven,three_rax_stim,two_base_tanks,tank_thor_mech,battle_cruisers,marine_rush,rusty,banshees,raven_liberator_tank}"
DIFFICULTIES="${DIFFICULTIES:-veryeasy,medium,hard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"
REPEATS="${REPEATS:-5}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
CONCURRENCY="${CONCURRENCY:-20}"

# 10 strategies x 3 races x 3 difficulties x 5 repeats = 450 jobs
TOTAL_JOBS=450

_start_sweep() {
  local which="$1"
  local session batch executor_model executor_mode

  case "$which" in
    grpo)
      session="${TMUX_SESSION_GRPO:-bo_exec_grpo_10strat_sweep}"
      batch="${BATCH_NAME_GRPO:-bo_exec_grpo_2x4ep_10strat_macro_r5}"
      executor_model="Qwen3-1.7b-sc2-executor-grpo-2x-4ep_think"
      executor_mode="thinking (GRPO 2x-4ep)"
      ;;
    17b_think)
      session="${TMUX_SESSION_17B:-bo_exec_17b_think_10strat_sweep}"
      batch="${BATCH_NAME_17B:-bo_exec_17b_think_10strat_macro_r5}"
      executor_model="Qwen3-1.7b_think"
      executor_mode="thinking (base 1.7B)"
      ;;
    27b)
      session="${TMUX_SESSION_27B:-bo_exec_27b_10strat_sweep}"
      batch="${BATCH_NAME_27B:-bo_exec_27b_10strat_macro_r5}"
      executor_model="Qwen35-27b"
      executor_mode="no thinking (27B)"
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

  pkill -f "run_bo_list_strategy_sweep.py --batch-name ${batch}" 2>/dev/null || true
  pkill -f "run_vs_ai.*--batch-name ${batch}" 2>/dev/null || true
  sleep 1

  tmux new-session -d -s "$session" -n sweep \
    "cd $(printf '%q' "$ROOT") && \
BATCH_NAME=$(printf '%q' "$batch") \
CONCURRENCY=$(printf '%q' "$CONCURRENCY") \
REPEATS=$(printf '%q' "$REPEATS") \
GAME_TIME_LIMIT=$(printf '%q' "$GAME_TIME_LIMIT") \
START_INDEX=$(printf '%q' "${START_INDEX:-0}") \
EXECUTOR_MODEL=$(printf '%q' "$executor_model") \
STRATEGIES=$(printf '%q' "$STRATEGIES") \
DIFFICULTIES=$(printf '%q' "$DIFFICULTIES") \
ENEMY_RACES=$(printf '%q' "$ENEMY_RACES") \
ENEMY_BUILD=$(printf '%q' "$ENEMY_BUILD") \
MAPS=$(printf '%q' "$MAPS") \
bash $(printf \'%q\' "$SCRIPT_DIR/run_bo_exec_sweep_tmux.sh")"
  echo "=================================================="
  echo " Started : $which"
  echo " Tmux    : $session"
  echo " Batch   : game_records/${batch}/"
  echo " Mode    : BO-list (executor only)"
  echo " Exec    : ${executor_model} (${executor_mode})"
  echo " Map     : KairosJunctionLE | build=macro"
  echo " Diffs   : ${DIFFICULTIES}"
  echo " Jobs    : ${TOTAL_JOBS} (10 strategies x 3 races x 3 diffs x 5 reps)"
  echo " Concur  : ${CONCURRENCY}"
  echo " Attach  : tmux attach -t ${session}"
  echo " Logs    : game_records/${batch}_stdout.log"
  echo "=================================================="
}

TARGET="${1:-}"
case "$TARGET" in
  grpo|17b_think|27b)
    _start_sweep "$TARGET"
    ;;
  all)
    _start_sweep grpo
    echo ""
    _start_sweep 17b_think
    echo ""
    _start_sweep 27b
    ;;
  "")
    echo "Usage: $0 {grpo|17b_think|27b|all}" >&2
    echo "  grpo      — Qwen3-1.7b-sc2-executor-grpo-2x-4ep_think (thinking)" >&2
    echo "  17b_think — Qwen3-1.7b_think (thinking)" >&2
    echo "  27b       — Qwen35-27b (no thinking)" >&2
    echo "  all       — launch all three in separate tmux sessions" >&2
    exit 1
    ;;
  *)
    echo "Unknown target: $TARGET (use grpo, 17b_think, 27b, or all)" >&2
    exit 1
    ;;
esac
