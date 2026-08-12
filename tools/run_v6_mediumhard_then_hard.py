"""Finish v5 accounting, run v6 MediumHard60, and conditionally run Hard60."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


ROOT = Path("/data2/shy_2608/SC2trace2nl/SC2-Agent-human-skill")
PYTHON = Path("/home/wyq/miniconda3/bin/python")
V5_BATCH = "human_skill_deepseek_flash_nothinking_fullv5_60_mediumhard_20260811"
V6_MEDIUM_BATCH = "human_skill_deepseek_flash_nothinking_fullv6_60_mediumhard_20260811"
V6_HARD_BATCH = "human_skill_deepseek_flash_nothinking_fullv6_60_hard_20260811"
TARGET_WINS = 30


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def process_is_target(pid: int, batch: str) -> bool:
    try:
        command = (Path("/proc") / str(pid) / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return False
    return "run_human_skill_reference_topology.py" in command and batch in command


def analyze(batch: str, method: str, filename: str) -> tuple[Path, dict]:
    output = ROOT / "game_records/_human_skill_ablation" / batch / filename
    subprocess.run(
        [
            str(PYTHON),
            "tools/analyze_human_skill_ablation.py",
            "--batch-prefix", batch,
            "--methods", method,
            "--baseline", method,
            "--output", str(output),
        ],
        cwd=ROOT,
        check=True,
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    return output, report["aggregate"][method]


def run_topology(batch: str, difficulty: str, offset: int) -> int:
    command = [
        str(PYTHON),
        "tools/run_human_skill_reference_topology.py",
        "--method", "full_v6",
        "--model", "DeepSeek-V4-flash",
        "--batch-prefix", batch,
        "--difficulty", difficulty,
        "--game-time-limit", "1200",
    ]
    if offset:
        command.extend(["--repeats", "4", "--run-index-offset", str(offset)])
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def result_summary(aggregate: dict) -> dict:
    results = aggregate.get("results", {})
    wins = int(results.get("Victory", 0))
    n = int(aggregate.get("n", 0))
    return {
        "n": n,
        "wins": wins,
        "ties": int(results.get("Tie", 0)),
        "defeats": int(results.get("Defeat", 0)),
        "pure_win_rate": round(wins / n, 6) if n else 0.0,
        "outcome_score": float(aggregate.get("outcome_score", 0.0)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v5-pid", type=int, required=True)
    args = parser.parse_args()
    status_path = ROOT / "game_records/_human_skill_ablation" / V6_MEDIUM_BATCH / "iteration_status.json"
    state = {"state": "waiting_for_v5", "target_wins": TARGET_WINS, "v5_pid": args.v5_pid}
    atomic_json(status_path, state)
    while process_is_target(args.v5_pid, V5_BATCH):
        time.sleep(30)

    v5_report, v5 = analyze(V5_BATCH, "full_v5", "analysis_full_v5_60.json")
    state.update({"v5_report": str(v5_report), "v5": result_summary(v5)})
    if state["v5"]["n"] != 60:
        state["state"] = "blocked_v5_not_60_clean"
        atomic_json(status_path, state)
        return 2

    state["state"] = "running_v6_mediumhard_0_29"
    atomic_json(status_path, state)
    first = run_topology(V6_MEDIUM_BATCH, "mediumhard", 0)
    state["mediumhard_first_returncode"] = first
    if first:
        state["state"] = "failed_v6_mediumhard_0_29"
        atomic_json(status_path, state)
        return first

    state["state"] = "running_v6_mediumhard_30_59"
    atomic_json(status_path, state)
    second = run_topology(V6_MEDIUM_BATCH, "mediumhard", 30)
    state["mediumhard_second_returncode"] = second
    if second:
        state["state"] = "failed_v6_mediumhard_30_59"
        atomic_json(status_path, state)
        return second

    medium_report, medium = analyze(V6_MEDIUM_BATCH, "full_v6", "analysis_full_v6_60.json")
    state.update({"mediumhard_report": str(medium_report), "mediumhard": result_summary(medium)})
    if state["mediumhard"]["n"] != 60:
        state["state"] = "blocked_v6_mediumhard_not_60_clean"
        atomic_json(status_path, state)
        return 2
    if state["mediumhard"]["wins"] < TARGET_WINS:
        state["state"] = "mediumhard_below_target_iteration_required"
        atomic_json(status_path, state)
        return 0

    state["state"] = "running_v6_hard_0_29"
    atomic_json(status_path, state)
    hard_first = run_topology(V6_HARD_BATCH, "hard", 0)
    state["hard_first_returncode"] = hard_first
    if hard_first:
        state["state"] = "failed_v6_hard_0_29"
        atomic_json(status_path, state)
        return hard_first

    state["state"] = "running_v6_hard_30_59"
    atomic_json(status_path, state)
    hard_second = run_topology(V6_HARD_BATCH, "hard", 30)
    state["hard_second_returncode"] = hard_second
    if hard_second:
        state["state"] = "failed_v6_hard_30_59"
        atomic_json(status_path, state)
        return hard_second

    hard_report, hard = analyze(V6_HARD_BATCH, "full_v6", "analysis_full_v6_hard_60.json")
    state.update({"hard_report": str(hard_report), "hard": result_summary(hard)})
    state["state"] = "complete" if state["hard"]["n"] == 60 else "blocked_v6_hard_not_60_clean"
    atomic_json(status_path, state)
    return 0 if state["state"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
