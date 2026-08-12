"""Retest 7 strategies with DeepSeek-V4-flash: 60 mediumhard games, concurrency 30."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path("/data2/shy_2608/SC2trace2nl/SC2-Agent-human-skill")
PYTHON = Path("/home/wyq/miniconda3/bin/python")
BATCH = "human_skill_deepseek_flash_nothinking_ablation7_60_mediumhard_20260812"
MODEL = "DeepSeek-V4-flash"
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


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def run_topology(method: str, offset: int) -> int:
    command = [
        str(PYTHON),
        "tools/run_human_skill_reference_topology.py",
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
    ]
    if offset:
        command.extend(["--repeats", "4", "--run-index-offset", str(offset)])
    return subprocess.run(command, cwd=ROOT, check=False).returncode


def analyze() -> Path:
    output = ROOT / "game_records/_human_skill_ablation" / BATCH / "analysis_ablation7_mediumhard_60.json"
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
        "target_games_per_method": 60,
        "concurrency": 30,
        "method_results": {},
    }
    atomic_json(STATUS_PATH, state)

    for method in METHODS:
        for offset, label in ((0, "0_29"), (30, "30_59")):
            state["state"] = f"running_{method}_{label}"
            atomic_json(STATUS_PATH, state)
            code = run_topology(method, offset)
            state.setdefault("returncodes", {})[f"{method}_{label}"] = code
            if code:
                state["state"] = f"failed_{method}_{label}"
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
