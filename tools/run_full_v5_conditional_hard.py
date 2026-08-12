"""Wait for Full-v5 MediumHard, analyze it, and conditionally run Hard 60."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path


ROOT = Path("/data2/shy_2608/SC2trace2nl/SC2-Agent-human-skill")
PYTHON = Path("/home/wyq/miniconda3/bin/python")
MEDIUM_BATCH = "human_skill_deepseek_flash_nothinking_fullv5_60_mediumhard_20260811"
HARD_BATCH = "human_skill_deepseek_flash_nothinking_fullv5_60_hard_20260811"
V3_SCORE = 0.45


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temp.replace(path)


def process_is_target(pid: int) -> bool:
    try:
        cmdline = (Path("/proc") / str(pid) / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
    except OSError:
        return False
    return "run_human_skill_reference_topology.py" in cmdline and MEDIUM_BATCH in cmdline


def analyze(batch: str, filename: str) -> tuple[Path, dict]:
    output = ROOT / "game_records/_human_skill_ablation" / batch / filename
    subprocess.run(
        [str(PYTHON), "tools/analyze_human_skill_ablation.py", "--batch-prefix", batch,
         "--methods", "full_v5", "--baseline", "full_v5", "--output", str(output)],
        cwd=ROOT, check=True,
    )
    report = json.loads(output.read_text(encoding="utf-8"))
    return output, report["aggregate"]["full_v5"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--medium-pid", type=int, required=True)
    args = parser.parse_args()
    status_path = ROOT / "game_records/_human_skill_ablation" / MEDIUM_BATCH / "conditional_status.json"
    atomic_json(status_path, {"state": "waiting_mediumhard", "medium_pid": args.medium_pid, "v3_score": V3_SCORE})
    while process_is_target(args.medium_pid):
        time.sleep(60)

    medium_report, medium = analyze(MEDIUM_BATCH, "analysis_full_v5_60.json")
    state = {
        "state": "mediumhard_analyzed", "medium_report": str(medium_report),
        "medium_n": int(medium["n"]), "medium_outcome_score": float(medium["outcome_score"]),
        "v3_outcome_score": V3_SCORE,
    }
    atomic_json(status_path, state)
    if int(medium["n"]) != 60:
        state["state"] = "hard_not_started_incomplete_mediumhard"
        atomic_json(status_path, state)
        return 2
    if float(medium["outcome_score"]) <= V3_SCORE:
        state["state"] = "hard_not_started_no_strict_improvement"
        atomic_json(status_path, state)
        return 0

    state["state"] = "running_hard"
    atomic_json(status_path, state)
    completed = subprocess.run(
        [str(PYTHON), "tools/run_human_skill_reference_topology.py", "--method", "full_v5",
         "--model", "DeepSeek-V4-flash", "--batch-prefix", HARD_BATCH,
         "--difficulty", "hard", "--game-time-limit", "1200"],
        cwd=ROOT, check=False,
    )
    state["hard_wrapper_returncode"] = completed.returncode
    if completed.returncode != 0:
        state["state"] = "hard_wrapper_failed"
        atomic_json(status_path, state)
        return completed.returncode
    hard_report, hard = analyze(HARD_BATCH, "analysis_full_v5_hard_60.json")
    state.update({
        "state": "complete", "hard_report": str(hard_report),
        "hard_n": int(hard["n"]), "hard_outcome_score": float(hard["outcome_score"]),
    })
    atomic_json(status_path, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
