"""Launch 10 diverse SC2 smoke matches for each structural baseline mode."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (bot_race, strategy, enemy_race, difficulty)
PLAN_EXECUTE_JOBS = [
    ("terran", "marine_rush", "zerg", "easy"),
    ("terran", "bio", "protoss", "medium"),
    ("terran", "blueflame_locks", "terran", "mediumhard"),
    ("terran", "two_base_matrix_tanks", "zerg", "hard"),
    ("terran", "yamato_rust_fleet", "protoss", "harder"),
    ("protoss", "four_gate", "terran", "easy"),
    ("protoss", "dark_templar_rush", "zerg", "medium"),
    ("protoss", "robo", "protoss", "mediumhard"),
    ("zerg", "twelve_pool", "terran", "hard"),
    ("zerg", "macro_roach", "protoss", "harder"),
]

SELF_REFINE_JOBS = [
    ("terran", "marine_rush", "protoss", "easy"),
    ("terran", "bio", "zerg", "medium"),
    ("terran", "blueflame_locks", "terran", "hard"),
    ("protoss", "four_gate", "zerg", "easy"),
    ("protoss", "voidray", "terran", "medium"),
    ("protoss", "macro_stalkers", "protoss", "harder"),
    ("zerg", "twelve_pool", "protoss", "medium"),
    ("zerg", "macro_roach", "terran", "mediumhard"),
    ("zerg", "roach_hydra", "zerg", "hard"),
    ("zerg", "mutalisk", "terran", "harder"),
]

SUNTZU_JOBS = [
    ("terran", "marine_rush", "zerg", "easy"),
    ("terran", "bio", "protoss", "medium"),
    ("terran", "yamato_rust_fleet", "terran", "hard"),
    ("protoss", "four_gate", "zerg", "easy"),
    ("protoss", "dark_templar_rush", "terran", "mediumhard"),
    ("protoss", "robo", "protoss", "harder"),
    ("zerg", "twelve_pool", "terran", "medium"),
    ("zerg", "macro_roach", "protoss", "hard"),
    ("zerg", "lurkers", "zerg", "mediumhard"),
    ("zerg", "mutalisk", "terran", "harder"),
]

HIMA_JOBS = [
    ("terran", "marine_rush", "protoss", "easy"),
    ("terran", "blueflame_locks", "zerg", "medium"),
    ("terran", "two_base_matrix_tanks", "terran", "harder"),
    ("protoss", "four_gate", "terran", "medium"),
    ("protoss", "voidray", "zerg", "hard"),
    ("protoss", "macro_stalkers", "protoss", "easy"),
    ("zerg", "twelve_pool", "protoss", "hard"),
    ("zerg", "roach_hydra", "terran", "mediumhard"),
    ("zerg", "macro_roach", "zerg", "medium"),
    ("zerg", "mutalisk", "protoss", "harder"),
]

COS_JOBS = [
    ("terran", "marine_rush", "terran", "easy"),
    ("terran", "bio", "zerg", "mediumhard"),
    ("terran", "blueflame_locks", "protoss", "hard"),
    ("protoss", "four_gate", "protoss", "medium"),
    ("protoss", "dark_templar_rush", "zerg", "harder"),
    ("protoss", "robo", "terran", "easy"),
    ("zerg", "twelve_pool", "zerg", "medium"),
    ("zerg", "macro_roach", "terran", "hard"),
    ("zerg", "roach_hydra", "protoss", "mediumhard"),
    ("zerg", "lurkers", "terran", "harder"),
]

MODE_JOBS = {
    "plan-execute": PLAN_EXECUTE_JOBS,
    "self-refine": SELF_REFINE_JOBS,
    "suntzu": SUNTZU_JOBS,
    "hima": HIMA_JOBS,
    "cos": COS_JOBS,
}


def _launch(job_index: int, mode: str, batch: str, job: tuple[str, str, str, str], args) -> int:
    bot_race, strategy, enemy_race, difficulty = job
    cmd = [
        sys.executable,
        str(ROOT / "tools" / "run_experiment.py"),
        "--decision-agent-mode",
        mode,
        "--decision-model",
        args.decision_model,
        "--data-subagent-model",
        args.decision_model,
        "--strategy",
        strategy,
        "--bot-race",
        bot_race,
        "--enemy-race",
        enemy_race,
        "--enemy-difficulty",
        difficulty,
        "--enemy-build",
        args.enemy_build,
        "--map-name",
        args.map_name,
        "--decision-interval",
        str(args.decision_interval),
        "--game-time-limit",
        str(args.game_time_limit),
        "--batch-name",
        batch,
        "--run-index",
        str(job_index),
        "--match-prefix",
        f"{bot_race[0]}_{strategy}_{enemy_race[0]}_{difficulty}",
    ]
    env = os.environ.copy()
    env["SC2PATH"] = args.sc2path
    env["SC2_GAME_TIME_LIMIT"] = str(args.game_time_limit)
    print(
        f"[{mode}][{job_index}] start {bot_race}/{strategy} vs "
        f"{enemy_race}/{difficulty}",
        flush=True,
    )
    completed = subprocess.run(cmd, cwd=str(ROOT), env=env)
    print(
        f"[{mode}][{job_index}] exit={completed.returncode} "
        f"{bot_race}/{strategy} vs {enemy_race}/{difficulty}",
        flush=True,
    )
    return completed.returncode


def _batch_name(mode: str, args) -> str:
    overrides = {
        "plan-execute": args.plan_execute_batch,
        "self-refine": args.self_refine_batch,
        "suntzu": args.suntzu_batch,
        "hima": args.hima_batch,
        "cos": args.cos_batch,
    }
    return overrides[mode]


def _run_mode(mode: str, jobs: list[tuple[str, str, str, str]], args) -> list[int]:
    batch = _batch_name(mode, args)
    codes: list[int] = []
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = []
        for index, job in enumerate(jobs):
            if futures:
                time.sleep(max(0.0, args.launch_stagger_seconds))
            futures.append(pool.submit(_launch, index, mode, batch, job, args))
        for future in as_completed(futures):
            codes.append(future.result())
    return codes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-model", default="qwen3-32b")
    parser.add_argument("--game-time-limit", type=int, default=360)
    parser.add_argument("--decision-interval", type=float, default=60.0)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--launch-stagger-seconds", type=float, default=1.0)
    parser.add_argument("--enemy-build", default="macro")
    parser.add_argument("--map-name", default="KairosJunctionLE")
    parser.add_argument("--sc2path", default="/data2/SC2/StarCraftII/")
    parser.add_argument(
        "--plan-execute-batch",
        default="smoke10_plan_execute_qwen3_32b_20260810",
    )
    parser.add_argument(
        "--self-refine-batch",
        default="smoke10_self_refine_qwen3_32b_20260810",
    )
    parser.add_argument(
        "--suntzu-batch",
        default="smoke10_suntzu_qwen3_32b_20260810",
    )
    parser.add_argument(
        "--hima-batch",
        default="smoke10_hima_qwen3_32b_20260810",
    )
    parser.add_argument(
        "--cos-batch",
        default="smoke10_cos_qwen3_32b_20260810",
    )
    parser.add_argument(
        "--modes",
        default="plan-execute,self-refine,suntzu,hima,cos",
        help="Comma-separated modes to run.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    selected = [item.strip() for item in args.modes.split(",") if item.strip()]
    unknown = [mode for mode in selected if mode not in MODE_JOBS]
    if unknown:
        raise SystemExit(f"Unsupported modes: {unknown}; expected {sorted(MODE_JOBS)}")
    if args.dry_run:
        for mode in selected:
            for i, job in enumerate(MODE_JOBS[mode]):
                print(f"{mode}[{i}] {job}")
        return 0

    all_codes: list[int] = []
    for mode in selected:
        all_codes.extend(_run_mode(mode, MODE_JOBS[mode], args))
    failed = sum(1 for code in all_codes if code != 0)
    print(f"DONE matches={len(all_codes)} failed_exits={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
