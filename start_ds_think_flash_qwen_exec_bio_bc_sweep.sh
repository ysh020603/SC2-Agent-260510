#!/usr/bin/env bash
# bio + battle_cruisers vs 3 races (macro) @ KairosJunctionLE
# naming/ordering: DeepSeek-V4-flash_think (thinking)
# executor: Qwen35-27b
# difficulties: veryeasy, medium, hard | 3 repeats per combo
#
# Usage:
#   bash start_ds_think_flash_qwen_exec_bio_bc_sweep.sh
# Resume (after pause): see game_records/ds_think_flash_qwen_exec_bio_bc_r3.PAUSED.json
#   START_INDEX=8 bash start_ds_think_flash_qwen_exec_bio_bc_sweep.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

SESSION="${TMUX_SESSION:-ds_think_flash_qwen_exec_bio_bc_sweep}"
BATCH_NAME="${BATCH_NAME:-ds_think_flash_qwen_exec_bio_bc_r3}"
CONCURRENCY="${CONCURRENCY:-3}"
REPEATS="${REPEATS:-3}"
STRATEGIES="${STRATEGIES:-bio,battle_cruisers}"
DIFFICULTIES="${DIFFICULTIES:-veryeasy,medium,hard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Killing existing tmux session: $SESSION"
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  sleep 1
fi

pkill -f "run_kimi_nothink_strategy_sweep.py --batch-name ${BATCH_NAME}" 2>/dev/null || true
pkill -f "run_experiment.py.*--batch-name ${BATCH_NAME}" 2>/dev/null || true
sleep 1

tmux new-session -d -s "$SESSION" -n sweep \
  "cd $(printf '%q' "$ROOT") && \
BATCH_NAME=$(printf '%q' "$BATCH_NAME") \
CONCURRENCY=$(printf '%q' "$CONCURRENCY") \
REPEATS=$(printf '%q' "$REPEATS") \
GAME_TIME_LIMIT=$(printf '%q' "$GAME_TIME_LIMIT") \
START_INDEX=$(printf '%q' "${START_INDEX:-0}") \
NAMING_MODEL=DeepSeek-V4-flash_think \
ORDERING_MODEL=DeepSeek-V4-flash_think \
EXECUTOR_MODEL=Qwen35-27b \
STRATEGIES=$(printf '%q' "$STRATEGIES") \
DIFFICULTIES=$(printf '%q' "$DIFFICULTIES") \
ENEMY_RACES=$(printf '%q' "$ENEMY_RACES") \
ENEMY_BUILD=$(printf '%q' "$ENEMY_BUILD") \
MAPS=$(printf '%q' "$MAPS") \
bash tools/run_strategy_sweep_tmux.sh"

echo "=================================================="
echo " Tmux session      : $SESSION"
echo " Batch folder      : game_records/${BATCH_NAME}/"
echo " Map               : KairosJunctionLE"
echo " Naming/Ordering   : DeepSeek-V4-flash_think (thinking)"
echo " Executor          : Qwen35-27b"
echo " Strategies        : ${STRATEGIES}"
echo " Opponent          : protoss,terran,zerg | build=macro"
echo " Difficulties      : ${DIFFICULTIES}"
echo " Repeats           : ${REPEATS} per combo"
echo " Concurrency       : ${CONCURRENCY}"
echo " Total jobs        : 54 (2 x 3 x 3 x 3)"
echo " Attach            : tmux attach -t $SESSION"
echo " Logs              : game_records/${BATCH_NAME}_stdout.log"
echo "=================================================="
