#!/usr/bin/env bash
# 10 Terran strategies vs 3 races (macro) @ KairosJunctionLE
# Hybrid: Qwen3-1.7b (or naming SFT) for naming, Qwen35-27b for ordering + executor
# Protocol aligned with game_records/bio_bc_3race_macro_experiment_results.md (Qwen batches)
#
# Usage:
#   bash tools/start_qwen17b_naming_27b_exec_10strat_macro_sweep.sh base   # Qwen3-1.7b naming
#   bash tools/start_qwen17b_naming_27b_exec_10strat_macro_sweep.sh sft     # Qwen3-1.7b-sc2-naming-sft
#   bash tools/start_qwen17b_naming_27b_exec_10strat_macro_sweep.sh grpo    # Qwen3-1.7b-sc2-naming-grpo-v2 (thinking)
#   bash tools/start_qwen17b_naming_27b_exec_10strat_macro_sweep.sh both   # launch both (separate tmux)
# Resume: START_INDEX=N bash tools/start_qwen17b_naming_27b_exec_10strat_macro_sweep.sh base

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
CONCURRENCY="${CONCURRENCY:-5}"
ORDERING_MODEL="${ORDERING_MODEL:-Qwen35-27b}"
EXECUTOR_MODEL="${EXECUTOR_MODEL:-Qwen35-27b}"

# 10 strategies x 3 races x 3 difficulties x 5 repeats = 450 jobs
TOTAL_JOBS=450

_start_sweep() {
  local which="$1"
  local session batch naming_model naming_mode

  case "$which" in
    base)
      session="${TMUX_SESSION_BASE:-qwen17b_base_naming_27b_exec_10strat_sweep}"
      batch="${BATCH_NAME_BASE:-qwen17b_base_naming_27b_exec_10strat_macro_r5}"
      naming_model="Qwen3-1.7b"
      naming_mode="no thinking"
      ;;
    sft)
      session="${TMUX_SESSION_SFT:-qwen17b_sft_naming_27b_exec_10strat_sweep}"
      batch="${BATCH_NAME_SFT:-qwen17b_sft_naming_27b_exec_10strat_macro_r5}"
      naming_model="Qwen3-1.7b-sc2-naming-sft"
      naming_mode="no thinking"
      ;;
    grpo)
      session="${TMUX_SESSION_GRPO:-qwen17b_grpo_v2_naming_27b_exec_10strat_sweep}"
      batch="${BATCH_NAME_GRPO:-qwen17b_grpo_v2_naming_27b_exec_10strat_macro_r5}"
      naming_model="Qwen3-1.7b-sc2-naming-grpo-v2_think"
      naming_mode="thinking"
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
NAMING_MODEL=$(printf '%q' "$naming_model") \
ORDERING_MODEL=$(printf '%q' "$ORDERING_MODEL") \
EXECUTOR_MODEL=$(printf '%q' "$EXECUTOR_MODEL") \
STRATEGIES=$(printf '%q' "$STRATEGIES") \
DIFFICULTIES=$(printf '%q' "$DIFFICULTIES") \
ENEMY_RACES=$(printf '%q' "$ENEMY_RACES") \
ENEMY_BUILD=$(printf '%q' "$ENEMY_BUILD") \
MAPS=$(printf '%q' "$MAPS") \
bash $(printf \'%q\' "$SCRIPT_DIR/run_strategy_sweep_tmux.sh")"
  echo "=================================================="
  echo " Started : $which"
  echo " Tmux    : $session"
  echo " Batch   : game_records/${batch}/"
  echo " Naming  : ${naming_model} (${naming_mode})"
  echo " Order   : ${ORDERING_MODEL}"
  echo " Exec    : ${EXECUTOR_MODEL}"
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
  base|sft|grpo)
    _start_sweep "$TARGET"
    ;;
  both)
    _start_sweep base
    echo ""
    _start_sweep sft
    ;;
  "")
    echo "Usage: $0 {base|sft|grpo|both}" >&2
    echo "  base  — Qwen3-1.7b naming + Qwen35-27b order/exec" >&2
    echo "  sft   — Qwen3-1.7b-sc2-naming-sft naming + Qwen35-27b order/exec" >&2
    echo "  grpo  — Qwen3-1.7b-sc2-naming-grpo-v2 naming (thinking) + Qwen35-27b order/exec" >&2
    echo "  both  — launch both base and sft sweeps in separate tmux sessions" >&2
    exit 1
    ;;
  *)
    echo "Unknown target: $TARGET (use base, sft, grpo, or both)" >&2
    exit 1
    ;;
esac
