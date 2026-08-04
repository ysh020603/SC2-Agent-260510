#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ $# -eq 0 ]]; then
  echo "usage: $0 --config experiment_configs/local/<name>.json [runner options]" >&2
  exit 2
fi

exec python tools/run_experiment_config.py --backend tmux "$@"
