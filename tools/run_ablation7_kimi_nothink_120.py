"""Retest 7 strategies with Kimi-k2.5 nothinking: 120 mediumhard games, concurrency 15."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path


ROOT = Path("/data2/shy_2608/SC2trace2nl/SC2-Agent-human-skill")
PYTHON = Path("/home/wyq/miniconda3/bin/python")
BATCH = "human_skill_kimi_k25_nothinking_ablation7_120_mediumhard_20260812"
MODEL = "Kimi-k2.5"
METHODS = (
    "full",
    "full_v7",
    "single_trace",
    "static_population",
    "flat_adaptive",
    "positive_only",
    "frequency_only",
)
STATUS_PATH = ROOT / "game_records/_human_skill_ablation" / BATCH / "iteration_status.json"
DEEPSEEK_STATUS = (
    ROOT
    / "game_records/_human_skill_ablation"
    / "human_skill_deepseek_flash_nothinking_ablation7_60_mediumhard_20260812"
    / "iteration_status.json"
)


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def wait_for_deepseek(state: dict) -> None:
    """Avoid stacking 30+15 SC2 children; start after DeepSeek suite finishes or fails."""
    state["state"] = "waiting_for_deepseek_suite"
    atomic_json(STATUS_PATH, state)
    while True:
        if not DEEPSEEK_STATUS.exists():
            time.sleep(30)
            continue
        try:
            payload = json.loads(DEEPSEEK_STATUS.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            time.sleep(30)
            continue
        ds_state = str(payload.get("state") or "")
        if ds_state in {"complete"} or ds_state.startswith("failed_") or ds_state.startswith("blocked_"):
            state["deepseek_wait_release"] = ds_state
            atomic_json(STATUS_PATH, state)
            return
        time.sleep(30)


def run_method(method: str) -> int:
    command = [
        str(PYTHON),
        "tools/run_human_skill_ablation_suite.py",
        "--method",
        method,
        "--model",
        MODEL,
        "--batch-prefix",
        BATCH,
        "--difficulty",
        "mediumhard",
        "--game-time-limit",
        "1200",
        "--repeats",
        "8",
        "--concurrency",
        "15",
        "--retry-concurrency",
        "1",
        "--launch-stagger",
        "2.0",
        "--max-attempts",
        "3",
        "--manifest-name",
        f"suite_manifest_{method}.json",
    ]
    log_path = ROOT / "game_records/_human_skill_ablation" / BATCH / f"suite_{method}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log:
        return subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False).returncode


def analyze() -> Path:
    output = ROOT / "game_records/_human_skill_ablation" / BATCH / "analysis_ablation7_mediumhard_120.json"
    subprocess.run(
        [
            str(PYTHON),
            "tools/analyze_human_skill_ablation.py",
            "--batch-prefix",
            BATCH,
            "--methods",
            ",".join(METHODS),
            "--baseline",
            "full",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=False,
    )
    return output


def main() -> int:
    state: dict = {
        "state": "starting",
        "batch": BATCH,
        "model": MODEL,
        "methods": list(METHODS),
        "target_games_per_method": 120,
        "concurrency": 15,
        "returncodes": {},
    }
    atomic_json(STATUS_PATH, state)
    wait_for_deepseek(state)

    for method in METHODS:
        state["state"] = f"running_{method}"
        atomic_json(STATUS_PATH, state)
        code = run_method(method)
        state["returncodes"][method] = code
        if code:
            state["state"] = f"failed_{method}"
            atomic_json(STATUS_PATH, state)
            return code

    report = analyze()
    state["analysis"] = str(report)
    if report.exists():
        payload = json.loads(report.read_text(encoding="utf-8"))
        state["aggregate"] = payload.get("aggregate", {})
    state["state"] = "complete"
    atomic_json(STATUS_PATH, state)
    print(json.dumps(state.get("aggregate", {}), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
