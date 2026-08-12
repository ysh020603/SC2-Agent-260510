"""Run 60 clean MediumHard games for V18, then 60 Hard games after the 30-win gate."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path("/data2/shy_2608/SC2trace2nl/SC2-Agent-human-skill")
PYTHON = Path("/home/wyq/miniconda3/bin/python")
MEDIUM_BATCH = "human_skill_deepseek_flash_nothinking_fullv18_60_mediumhard_20260812"
HARD_BATCH = "human_skill_deepseek_flash_nothinking_fullv18_60_hard_20260812"
METHOD = "full_v18"
VERSION = "v18"
TARGET_WINS = 30


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def summarize(aggregate: dict) -> dict:
    results = aggregate.get("results", {})
    n = int(aggregate.get("n", 0))
    wins = int(results.get("Victory", 0))
    return {
        "n": n, "wins": wins, "ties": int(results.get("Tie", 0)),
        "defeats": int(results.get("Defeat", 0)),
        "pure_win_rate": round(wins / n, 6) if n else 0.0,
        "outcome_score": float(aggregate.get("outcome_score", 0.0)),
    }


def analyze(batch: str, suffix: str) -> tuple[Path, dict]:
    output = ROOT / "game_records/_human_skill_ablation" / batch / f"analysis_{METHOD}_{suffix}_60.json"
    subprocess.run(
        [str(PYTHON), "tools/analyze_human_skill_ablation.py", "--batch-prefix", batch,
         "--methods", METHOD, "--baseline", METHOD, "--output", str(output)],
        cwd=ROOT, check=True,
    )
    return output, json.loads(output.read_text(encoding="utf-8"))["aggregate"][METHOD]


def run_topology(batch: str, difficulty: str, offset: int) -> int:
    command = [
        str(PYTHON), "tools/run_human_skill_reference_topology.py", "--method", METHOD,
        "--model", "DeepSeek-V4-flash", "--batch-prefix", batch, "--difficulty", difficulty,
        "--game-time-limit", "1200",
    ]
    if offset:
        command.extend(["--repeats", "4", "--run-index-offset", str(offset)])
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def run_stage(state: dict, status_path: Path, label: str, batch: str, difficulty: str) -> int:
    for offset, run_range in ((0, "0_29"), (30, "30_59")):
        state["state"] = f"running_{VERSION}_{label}_{run_range}"
        atomic_json(status_path, state)
        code = run_topology(batch, difficulty, offset)
        state[f"{label}_{run_range}_returncode"] = code
        if code:
            state["state"] = f"failed_{VERSION}_{label}_{run_range}"
            atomic_json(status_path, state)
            return code
    return 0


def main() -> int:
    status_path = ROOT / "game_records/_human_skill_ablation" / MEDIUM_BATCH / "iteration_status.json"
    state = {
        "state": "starting_v18_mediumhard", "target_wins": TARGET_WINS,
        "design": "v16-stable early/midgame with generic post-15-minute income-matched throughput closer",
    }
    atomic_json(status_path, state)
    code = run_stage(state, status_path, "mediumhard", MEDIUM_BATCH, "mediumhard")
    if code:
        return code
    report, aggregate = analyze(MEDIUM_BATCH, "mediumhard")
    state.update({"mediumhard_report": str(report), "mediumhard": summarize(aggregate)})
    if state["mediumhard"]["n"] != 60:
        state["state"] = "blocked_v18_mediumhard_not_60_clean"
        atomic_json(status_path, state)
        return 2
    if state["mediumhard"]["wins"] < TARGET_WINS:
        state["state"] = "mediumhard_below_target_iteration_required"
        atomic_json(status_path, state)
        return 0

    code = run_stage(state, status_path, "hard", HARD_BATCH, "hard")
    if code:
        return code
    report, aggregate = analyze(HARD_BATCH, "hard")
    state.update({"hard_report": str(report), "hard": summarize(aggregate)})
    state["state"] = "complete" if state["hard"]["n"] == 60 else "blocked_v18_hard_not_60_clean"
    atomic_json(status_path, state)
    return 0 if state["state"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
