"""Run branch-faithful v7 if v6 misses the MediumHard pure-win target."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


ROOT = Path("/data2/shy_2608/SC2trace2nl/SC2-Agent-human-skill")
PYTHON = Path("/home/wyq/miniconda3/bin/python")
V6_BATCH = "human_skill_deepseek_flash_nothinking_fullv6_60_mediumhard_20260811"
V7_MEDIUM_BATCH = "human_skill_deepseek_flash_nothinking_fullv7_60_mediumhard_20260811"
V7_HARD_BATCH = "human_skill_deepseek_flash_nothinking_fullv7_60_hard_20260811"
TARGET_WINS = 30


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def process_matches(pid: int, fragment: str) -> bool:
    try:
        command = (Path("/proc") / str(pid) / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return False
    return fragment in command


def analyze(batch: str, difficulty_suffix: str) -> tuple[Path, dict]:
    output = ROOT / "game_records/_human_skill_ablation" / batch / f"analysis_full_v7_{difficulty_suffix}_60.json"
    subprocess.run(
        [str(PYTHON), "tools/analyze_human_skill_ablation.py", "--batch-prefix", batch,
         "--methods", "full_v7", "--baseline", "full_v7", "--output", str(output)],
        cwd=ROOT, check=True,
    )
    return output, json.loads(output.read_text(encoding="utf-8"))["aggregate"]["full_v7"]


def summarize(aggregate: dict) -> dict:
    results = aggregate.get("results", {})
    n = int(aggregate.get("n", 0))
    wins = int(results.get("Victory", 0))
    return {
        "n": n,
        "wins": wins,
        "ties": int(results.get("Tie", 0)),
        "defeats": int(results.get("Defeat", 0)),
        "pure_win_rate": round(wins / n, 6) if n else 0.0,
        "outcome_score": float(aggregate.get("outcome_score", 0.0)),
    }


def run_topology(batch: str, difficulty: str, offset: int) -> int:
    command = [
        str(PYTHON), "tools/run_human_skill_reference_topology.py",
        "--method", "full_v7", "--model", "DeepSeek-V4-flash",
        "--batch-prefix", batch, "--difficulty", difficulty,
        "--game-time-limit", "1200",
    ]
    if offset:
        command.extend(["--repeats", "4", "--run-index-offset", str(offset)])
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def run_stage(state: dict, status_path: Path, label: str, batch: str, difficulty: str) -> int:
    for offset, suffix in ((0, "0_29"), (30, "30_59")):
        state["state"] = f"running_v7_{label}_{suffix}"
        atomic_json(status_path, state)
        returncode = run_topology(batch, difficulty, offset)
        state[f"{label}_{suffix}_returncode"] = returncode
        if returncode:
            state["state"] = f"failed_v7_{label}_{suffix}"
            atomic_json(status_path, state)
            return returncode
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v6-pid", type=int, required=True)
    args = parser.parse_args()
    status_path = ROOT / "game_records/_human_skill_ablation" / V7_MEDIUM_BATCH / "iteration_status.json"
    state = {"state": "waiting_for_v6", "target_wins": TARGET_WINS, "v6_pid": args.v6_pid}
    atomic_json(status_path, state)
    while process_matches(args.v6_pid, "run_v6_mediumhard_then_hard.py"):
        time.sleep(30)

    v6_status_path = ROOT / "game_records/_human_skill_ablation" / V6_BATCH / "iteration_status.json"
    v6_status = json.loads(v6_status_path.read_text(encoding="utf-8"))
    state["v6_state"] = v6_status.get("state")
    state["v6_mediumhard"] = v6_status.get("mediumhard", {})
    if v6_status.get("state") != "mediumhard_below_target_iteration_required":
        state["state"] = "not_started_v6_met_target_or_continued_to_hard"
        atomic_json(status_path, state)
        return 0

    returncode = run_stage(state, status_path, "mediumhard", V7_MEDIUM_BATCH, "mediumhard")
    if returncode:
        return returncode
    medium_report, medium = analyze(V7_MEDIUM_BATCH, "mediumhard")
    state.update({"mediumhard_report": str(medium_report), "mediumhard": summarize(medium)})
    if state["mediumhard"]["n"] != 60:
        state["state"] = "blocked_v7_mediumhard_not_60_clean"
        atomic_json(status_path, state)
        return 2
    if state["mediumhard"]["wins"] < TARGET_WINS:
        state["state"] = "mediumhard_below_target_iteration_required"
        atomic_json(status_path, state)
        return 0


    returncode = run_stage(state, status_path, "hard", V7_HARD_BATCH, "hard")
    if returncode:
        return returncode
    hard_report, hard = analyze(V7_HARD_BATCH, "hard")
    state.update({"hard_report": str(hard_report), "hard": summarize(hard)})
    state["state"] = "complete" if state["hard"]["n"] == 60 else "blocked_v7_hard_not_60_clean"
    atomic_json(status_path, state)
    return 0 if state["state"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
