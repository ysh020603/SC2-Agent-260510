"""Run the selected full-match matrix with configurable SC2 concurrency."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = "kn30"
MODEL = "Kimi-k2.5"
INTERVAL = 60
LIMIT = 1200
ENEMY_RACE = "terran"
ENEMY_DIFF = "easy"
CONCURRENCY = 5
START_STAGGER_SEC = 8
SESSION_ID = f"{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"


@dataclass(frozen=True)
class Job:
    index: int
    strategy: str
    bot_race: str
    map_name: str
    prefix: str


JOBS = [
    Job(0, "marine_rush", "terran", "KairosJunctionLE", "t_mrush_kj"),
    Job(1, "bio", "terran", "AutomatonLE", "t_bio_au"),
    Job(2, "two_base_matrix_tanks", "terran", "AbyssalReefLE", "t_2bmt_ab"),
    Job(3, "four_gate", "protoss", "AutomatonLE", "p_4gate_au"),
    Job(4, "voidray", "protoss", "AbyssalReefLE", "p_void_ab"),
    Job(5, "twelve_pool", "zerg", "KairosJunctionLE", "z_12pool_kj"),
    Job(6, "roach_hydra", "zerg", "AutomatonLE", "z_rh_au"),
]


def _valid_record_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    for result_path in path.glob("*.json"):
        if result_path.name.endswith(".llm_calls.json"):
            continue
        try:
            value = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(value, dict) and (
            "metadata" in value or "interactions" in value
        ):
            return True
    return False


def _completed(index: int) -> bool:
    root = ROOT / "game_records" / BATCH
    if not root.is_dir():
        return False
    suffix = f"_run{index}"
    return any(
        path.name.endswith(suffix) and _valid_record_dir(path)
        for path in root.iterdir()
    )


def _run_one(job: Job) -> tuple[int, str]:
    if _completed(job.index):
        return 0, f"[{job.index}] skipped: already completed"

    # Stagger launches so SC2 clients do not collide on startup ports.
    time.sleep(START_STAGGER_SEC * (job.index % CONCURRENCY))

    log_dir = ROOT / "game_records" / BATCH / "runner_logs" / SESSION_ID
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{job.index:02d}_{job.bot_race}_{job.strategy}_{job.map_name}.log"

    command = [
        sys.executable,
        str(ROOT / "tools" / "run_experiment.py"),
        "--strategy",
        job.strategy,
        "--bot-race",
        job.bot_race,
        "--enemy-race",
        ENEMY_RACE,
        "--enemy-difficulty",
        ENEMY_DIFF,
        "--decision-model",
        MODEL,
        "--decision-interval",
        str(INTERVAL),
        "--game-time-limit",
        str(LIMIT),
        "--map-name",
        job.map_name,
        "--batch-name",
        BATCH,
        "--match-prefix",
        job.prefix,
        "--run-index",
        str(job.index),
    ]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    print(
        f"[{job.index}] START {job.bot_race}/{job.strategy}@{job.map_name}",
        flush=True,
    )
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n===== start {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
        log.write("CMD: " + " ".join(command) + "\n")
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if _completed(job.index):
        return 0, f"[{job.index}] completed exit={result.returncode}"
    return result.returncode or 2, f"[{job.index}] failed exit={result.returncode}"


def main() -> int:
    print(
        f"batch={BATCH} model={MODEL} jobs={len(JOBS)} "
        f"concurrency={CONCURRENCY} limit={LIMIT}s",
        flush=True,
    )
    failures = 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [pool.submit(_run_one, job) for job in JOBS]
        for future in as_completed(futures):
            code, message = future.result()
            failures += int(code != 0)
            print(message, flush=True)
    print(f"finished: failures={failures}/{len(JOBS)}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
