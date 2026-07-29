#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TOTAL="${1:?usage: tools/run_vs_ai_batch.sh TOTAL [CONCURRENCY]}"
CONCURRENCY="${2:-1}"
DECISION_MODEL="${DECISION_MODEL:-Kimi-k2.5}"
DECISION_INTERVAL="${DECISION_INTERVAL:-60}"
FORCE_STRATEGY="${FORCE_STRATEGY:-marine_rush}"
BATCH_NAME="${BATCH_NAME:-batch_$(date +%Y%m%d_%H%M%S)}"

export ROOT DECISION_MODEL DECISION_INTERVAL FORCE_STRATEGY BATCH_NAME
seq 0 $((TOTAL - 1)) | xargs -P "$CONCURRENCY" -I '{}' bash -c '
  python "$ROOT/run_vs_ai.py" \
    --decision-model "$DECISION_MODEL" \
    --decision-interval "$DECISION_INTERVAL" \
    --force-strategy "$FORCE_STRATEGY" \
    --batch-name "$BATCH_NAME" \
    --run-index "{}" \
    --skip-version-update
'
