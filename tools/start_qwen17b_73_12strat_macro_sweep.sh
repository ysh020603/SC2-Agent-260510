#!/usr/bin/env bash
# 12 Terran strategies (6 old + 6 new) vs 3 races (macro) @ KairosJunctionLE
# Models on 172.18.30.73 thinking endpoints (*_73 / *_73b)
#
# Group trained: naming/ordering/executor = sc2-{naming,ordering,executor}_73
#   Dual replica: 8101-8103 (shard 0) + 8111-8113 (shard 1), concurrency 10 each
# Group base_order: ordering = Qwen3-1.7b_73 (untrained); naming/exec stay trained
# Group mix_cot: all three modules = sc2-mix-cot (8120 shard0 / 8121 shard1)
#
# Usage:
#   bash tools/start_qwen17b_73_12strat_macro_sweep.sh trained
#   bash tools/start_qwen17b_73_12strat_macro_sweep.sh mix_cot
#   bash tools/start_qwen17b_73_12strat_macro_sweep.sh base_order
# Resume: CONCURRENCY=10 SKIP_COMPLETED=1 bash tools/start_qwen17b_73_12strat_macro_sweep.sh trained

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found." >&2
  exit 1
fi

OLD_STRATEGIES="banshees,battle_cruisers,bio,cyclones,marine_rush,two_base_tanks"
NEW_STRATEGIES="raven_screams,yamato_rust_fleet,rusty_bio_mines,blueflame_locks,stim_rush_relay,two_base_matrix_tanks"
STRATEGIES="${STRATEGIES:-${OLD_STRATEGIES},${NEW_STRATEGIES}}"
DIFFICULTIES="${DIFFICULTIES:-veryeasy,medium,hard}"
ENEMY_RACES="${ENEMY_RACES:-protoss,terran,zerg}"
ENEMY_BUILD="${ENEMY_BUILD:-macro}"
MAPS="${MAPS:-KairosJunctionLE}"
REPEATS="${REPEATS:-5}"
GAME_TIME_LIMIT="${GAME_TIME_LIMIT:-1200}"
CONCURRENCY="${CONCURRENCY:-12}"
JOB_STRIDE="${JOB_STRIDE:-2}"

# 12 strategies x 3 races x 3 difficulties x 5 repeats = 540 jobs
TOTAL_JOBS=540

_kill_batch() {
  local batch="$1"
  pkill -f "run_kimi_nothink_strategy_sweep.py --batch-name ${batch}" 2>/dev/null || true
  pkill -f "run_experiment.py.*--batch-name ${batch}" 2>/dev/null || true
}

_start_shard() {
  local session="$1"
  local batch="$2"
  local naming_model="$3"
  local ordering_model="$4"
  local executor_model="$5"
  local job_offset="$6"
  local note="$7"
  local log_suffix="$8"

  if tmux has-session -t "$session" 2>/dev/null; then
    echo "Killing existing tmux session: $session"
    tmux kill-session -t "$session" 2>/dev/null || true
    sleep 1
  fi

  tmux new-session -d -s "$session" -n sweep \
    "cd $(printf '%q' "$ROOT") && \
BATCH_NAME=$(printf '%q' "$batch") \
CONCURRENCY=$(printf '%q' "$CONCURRENCY") \
REPEATS=$(printf '%q' "$REPEATS") \
GAME_TIME_LIMIT=$(printf '%q' "$GAME_TIME_LIMIT") \
START_INDEX=$(printf '%q' "${START_INDEX:-0}") \
SKIP_COMPLETED=$(printf '%q' "${SKIP_COMPLETED:-0}") \
JOB_STRIDE=$(printf '%q' "$JOB_STRIDE") \
JOB_OFFSET=$(printf '%q' "$job_offset") \
MAX_ATTEMPTS=$(printf '%q' "${MAX_ATTEMPTS:-3}") \
AUTO_EXIT=$(printf '%q' "${AUTO_EXIT:-0}") \
LOG_SUFFIX=$(printf '%q' "$log_suffix") \
NAMING_MODEL=$(printf '%q' "$naming_model") \
ORDERING_MODEL=$(printf '%q' "$ordering_model") \
EXECUTOR_MODEL=$(printf '%q' "$executor_model") \
STRATEGIES=$(printf '%q' "$STRATEGIES") \
DIFFICULTIES=$(printf '%q' "$DIFFICULTIES") \
ENEMY_RACES=$(printf '%q' "$ENEMY_RACES") \
ENEMY_BUILD=$(printf '%q' "$ENEMY_BUILD") \
MAPS=$(printf '%q' "$MAPS") \
bash $(printf '%q' "$SCRIPT_DIR/run_strategy_sweep_tmux.sh")"

  echo "--------------------------------------------------"
  echo " Started shard: ${note}"
  echo " Tmux         : ${session}"
  echo " Batch        : game_records/${batch}/"
  echo " Naming       : ${naming_model}"
  echo " Ordering     : ${ordering_model}"
  echo " Executor     : ${executor_model}"
  echo " Shard        : stride=${JOB_STRIDE} offset=${job_offset}"
  echo " Concurrency  : ${CONCURRENCY}"
  echo " Skip completed: ${SKIP_COMPLETED:-0}"
  echo " Attach       : tmux attach -t ${session}"
  echo " Logs         : game_records/${batch}${log_suffix}_stdout.log"
  echo "--------------------------------------------------"
}

_start_dual_replicas() {
  local which="$1"
  local batch session0 session1
  local n0 o0 e0 n1 o1 e1 note0 note1

  case "$which" in
    trained)
      batch="${BATCH_NAME_TRAINED:-qwen17b_73_trained_12strat_macro_r5}"
      session0="${TMUX_SESSION_TRAINED_A:-qwen17b_73_trained_12strat_macro_sweep_a}"
      session1="${TMUX_SESSION_TRAINED_B:-qwen17b_73_trained_12strat_macro_sweep_b}"
      n0="${NAMING_MODEL:-Qwen3-1.7b-sc2-naming_73}"
      o0="${ORDERING_MODEL:-Qwen3-1.7b-sc2-ordering_73}"
      e0="${EXECUTOR_MODEL:-Qwen3-1.7b-sc2-executor_73}"
      n1="${NAMING_MODEL_B:-Qwen3-1.7b-sc2-naming_73b}"
      o1="${ORDERING_MODEL_B:-Qwen3-1.7b-sc2-ordering_73b}"
      e1="${EXECUTOR_MODEL_B:-Qwen3-1.7b-sc2-executor_73b}"
      note0="trained replicaA 8101-8103"
      note1="trained replicaB 8111-8113"
      # resume by default for trained
      SKIP_COMPLETED="${SKIP_COMPLETED:-1}"
      ;;
    mix_cot)
      batch="${BATCH_NAME_MIXCOT:-qwen17b_73_mixcot_12strat_macro_r5}"
      session0="${TMUX_SESSION_MIXCOT_A:-qwen17b_73_mixcot_12strat_macro_sweep_a}"
      session1="${TMUX_SESSION_MIXCOT_B:-qwen17b_73_mixcot_12strat_macro_sweep_b}"
      n0="${NAMING_MODEL:-Qwen3-1.7b-sc2-mix-cot_73}"
      o0="${ORDERING_MODEL:-Qwen3-1.7b-sc2-mix-cot_73}"
      e0="${EXECUTOR_MODEL:-Qwen3-1.7b-sc2-mix-cot_73}"
      n1="${NAMING_MODEL_B:-Qwen3-1.7b-sc2-mix-cot_73b}"
      o1="${ORDERING_MODEL_B:-Qwen3-1.7b-sc2-mix-cot_73b}"
      e1="${EXECUTOR_MODEL_B:-Qwen3-1.7b-sc2-mix-cot_73b}"
      note0="mix_cot replicaA 8120"
      note1="mix_cot replicaB 8121"
      # Do not inherit SKIP_COMPLETED=1 from a prior trained launch in the same process.
      SKIP_COMPLETED="${MIXCOT_SKIP_COMPLETED:-0}"
      ;;
    *)
      echo "Unknown dual target: $which" >&2
      return 1
      ;;
  esac

  export SKIP_COMPLETED
  _kill_batch "$batch"
  sleep 1

  echo "=================================================="
  echo " Dual-replica sweep: ${which}"
  echo " Batch             : ${batch}"
  echo " Map/build         : KairosJunctionLE / macro"
  echo " Jobs              : ${TOTAL_JOBS} (sharded 2-way)"
  echo " Concurrency/shard : ${CONCURRENCY}  (total ~$((CONCURRENCY * 2)))"
  echo "=================================================="

  _start_shard "$session0" "$batch" "$n0" "$o0" "$e0" 0 "$note0" "_a"
  echo ""
  _start_shard "$session1" "$batch" "$n1" "$o1" "$e1" 1 "$note1" "_b"
}

_start_base_order() {
  local session="${TMUX_SESSION_BASE_ORDER:-qwen17b_73_base_order_12strat_macro_sweep}"
  local batch="${BATCH_NAME_BASE_ORDER:-qwen17b_73_base_order_12strat_macro_r5}"
  local naming_model="${NAMING_MODEL:-Qwen3-1.7b-sc2-naming_73}"
  local ordering_model="Qwen3-1.7b_73"
  local executor_model="${EXECUTOR_MODEL:-Qwen3-1.7b-sc2-executor_73}"

  _kill_batch "$batch"
  JOB_STRIDE=1
  SKIP_COMPLETED="${SKIP_COMPLETED:-0}"
  _start_shard "$session" "$batch" "$naming_model" "$ordering_model" "$executor_model" 0 \
    "base_order (single)" ""
}

_start_mix_cot_resume() {
  # Dual-API resume: both workers use stride=1 + skip-completed; job flock avoids races.
  # Replica A -> 8120 (*_73), replica B -> 8121 (*_73b).
  local batch="${BATCH_NAME_MIXCOT:-qwen17b_73_mixcot_12strat_macro_r5}"
  local session0="${TMUX_SESSION_MIXCOT_RESUME_A:-qwen17b_73_mixcot_12strat_macro_resume_a}"
  local session1="${TMUX_SESSION_MIXCOT_RESUME_B:-qwen17b_73_mixcot_12strat_macro_resume_b}"
  local n0="${NAMING_MODEL:-Qwen3-1.7b-sc2-mix-cot_73}"
  local o0="${ORDERING_MODEL:-Qwen3-1.7b-sc2-mix-cot_73}"
  local e0="${EXECUTOR_MODEL:-Qwen3-1.7b-sc2-mix-cot_73}"
  local n1="${NAMING_MODEL_B:-Qwen3-1.7b-sc2-mix-cot_73b}"
  local o1="${ORDERING_MODEL_B:-Qwen3-1.7b-sc2-mix-cot_73b}"
  local e1="${EXECUTOR_MODEL_B:-Qwen3-1.7b-sc2-mix-cot_73b}"

  # Stop all known mix_cot remainder/sweep sessions for this batch.
  for s in \
    qwen17b_73_mixcot_12strat_macro_sweep_a \
    qwen17b_73_mixcot_12strat_macro_sweep_b \
    qwen17b_73_mixcot_remainder_a \
    qwen17b_73_mixcot_remainder_serial \
    qwen17b_73_mixcot_12strat_macro_resume \
    "$session0" \
    "$session1"
  do
    if tmux has-session -t "$s" 2>/dev/null; then
      echo "Killing tmux session: $s"
      tmux kill-session -t "$s" 2>/dev/null || true
    fi
  done
  _kill_batch "$batch"
  sleep 2

  # Default matches prior dual-replica game concurrency (12/API). Override with CONCURRENCY=.
  JOB_STRIDE=1
  JOB_OFFSET=0
  SKIP_COMPLETED=1
  AUTO_EXIT=1
  CONCURRENCY="${CONCURRENCY:-12}"
  MAX_ATTEMPTS="${MAX_ATTEMPTS:-3}"
  export AUTO_EXIT MAX_ATTEMPTS SKIP_COMPLETED JOB_STRIDE JOB_OFFSET

  echo "=================================================="
  echo " mix_cot resume (dual API, shared job pool + flock)"
  echo " Batch          : ${batch}"
  echo " Concurrency/API: ${CONCURRENCY}  (total up to $((CONCURRENCY * 2)))"
  echo " Max attempts   : ${MAX_ATTEMPTS}"
  echo " APIs           : 8120 (*_73) + 8121 (*_73b)"
  echo " Skip done      : 1"
  echo "=================================================="

  _start_shard "$session0" "$batch" "$n0" "$o0" "$e0" 0 \
    "mix_cot resume A 8120" "_resume_a"
  echo ""
  _start_shard "$session1" "$batch" "$n1" "$o1" "$e1" 0 \
    "mix_cot resume B 8121" "_resume_b"
}

TARGET="${1:-}"
case "$TARGET" in
  trained|mix_cot)
    _start_dual_replicas "$TARGET"
    ;;
  mix_cot_resume)
    _start_mix_cot_resume
    ;;
  base_order)
    _start_base_order
    ;;
  both)
    _start_dual_replicas trained
    echo ""
    _start_base_order
    ;;
  trained_and_mixcot)
    _start_dual_replicas trained
    echo ""
    _start_dual_replicas mix_cot
    ;;
  "")
    echo "Usage: $0 {trained|mix_cot|mix_cot_resume|base_order|both|trained_and_mixcot}" >&2
    echo "  trained            — dual replica trained modules, concurrency/shard=${CONCURRENCY}" >&2
    echo "  mix_cot            — dual mix-cot for naming/ordering/executor" >&2
    echo "  mix_cot_resume     — single-session resume remaining mix_cot jobs (skip completed)" >&2
    echo "  base_order         — ordering = Qwen3-1.7b_73; naming/exec trained" >&2
    echo "  both               — trained + base_order" >&2
    echo "  trained_and_mixcot — trained + mix_cot dual replicas" >&2
    exit 1
    ;;
  *)
    echo "Unknown target: $TARGET" >&2
    exit 1
    ;;
esac
