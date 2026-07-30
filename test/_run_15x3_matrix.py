"""Full 15-strategy x 3-enemy complete-match matrix (Kimi-k2.5).

Concurrency default 5. Short batch/match names avoid Windows MAX_PATH.
Does not modify agent code.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = "k15"
MODEL = "Kimi-k2.5"
INTERVAL = 60
LIMIT = 1200
ENEMY_DIFF = "easy"
CONCURRENCY = 5
START_STAGGER_SEC = 6
MAX_ATTEMPTS = 2
SESSION_ID = f"{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"

MAPS = ["KairosJunctionLE", "AutomatonLE", "AbyssalReefLE"]
ENEMY_RACES = ["terran", "protoss", "zerg"]

STRATEGIES = [
    ("terran", "marine_rush"),
    ("terran", "bio"),
    ("terran", "blueflame_locks"),
    ("terran", "two_base_matrix_tanks"),
    ("terran", "yamato_rust_fleet"),
    ("protoss", "four_gate"),
    ("protoss", "dark_templar_rush"),
    ("protoss", "robo"),
    ("protoss", "voidray"),
    ("protoss", "macro_stalkers"),
    ("zerg", "twelve_pool"),
    ("zerg", "macro_roach"),
    ("zerg", "roach_hydra"),
    ("zerg", "lurkers"),
    ("zerg", "mutalisk"),
]

_print_lock = threading.Lock()


def _log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


@dataclass(frozen=True)
class Job:
    index: int
    bot_race: str
    strategy: str
    enemy_race: str
    map_name: str

    @property
    def prefix(self) -> str:
        # Keep short: r1 + strat<=5 + map2 + enemy1
        r = self.bot_race[0]
        s = self.strategy.replace("_", "")[:5]
        m = "".join(ch for ch in self.map_name if ch.isupper())[:2] or self.map_name[:2]
        e = self.enemy_race[0]
        return f"{r}{s}{m}{e}"


def _jobs() -> list[Job]:
    out: list[Job] = []
    for bot_race, strategy in STRATEGIES:
        for enemy_race in ENEMY_RACES:
            map_name = MAPS[len(out) % len(MAPS)]
            out.append(
                Job(
                    index=len(out),
                    bot_race=bot_race,
                    strategy=strategy,
                    enemy_race=enemy_race,
                    map_name=map_name,
                )
            )
    return out


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
    tag = (
        f"{job.bot_race}/{job.strategy}_vs_{job.enemy_race}@{job.map_name}"
    )
    if _completed(job.index):
        return 0, f"[{job.index:02d}] skipped: already completed {tag}"

    # Stagger within the concurrency window.
    time.sleep(START_STAGGER_SEC * (job.index % CONCURRENCY))

    log_dir = ROOT / "game_records" / BATCH / "runner_logs" / SESSION_ID
    log_dir.mkdir(parents=True, exist_ok=True)
    # Unique per job+attempt family; never share across jobs.
    log_path = log_dir / (
        f"{job.index:02d}_{job.bot_race}_{job.strategy}_vs_{job.enemy_race}_"
        f"{job.map_name}.log"
    )

    command = [
        sys.executable,
        str(ROOT / "tools" / "run_experiment.py"),
        "--strategy",
        job.strategy,
        "--bot-race",
        job.bot_race,
        "--enemy-race",
        job.enemy_race,
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

    _log(f"[{job.index:02d}] START {tag}")
    exit_code = 1
    for attempt in range(1, MAX_ATTEMPTS + 1):
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n===== attempt {attempt} {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
            log.write("CMD: " + " ".join(command) + "\n")
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
            exit_code = result.returncode
        if _completed(job.index):
            return 0, f"[{job.index:02d}] completed exit={exit_code} {tag}"
        if attempt < MAX_ATTEMPTS:
            time.sleep(min(attempt * 8, 20))
    return exit_code or 2, f"[{job.index:02d}] FAILED exit={exit_code} {tag}"


def main() -> int:
    jobs = _jobs()
    _log(
        f"batch={BATCH} model={MODEL} jobs={len(jobs)} "
        f"concurrency={CONCURRENCY} limit={LIMIT}s enemies={ENEMY_RACES}"
    )
    for job in jobs:
        _log(
            f"  plan[{job.index:02d}] {job.bot_race}/{job.strategy} vs "
            f"{job.enemy_race} @ {job.map_name} prefix={job.prefix}"
        )

    failures = 0
    done = 0
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [pool.submit(_run_one, job) for job in jobs]
        for future in as_completed(futures):
            code, message = future.result()
            failures += int(code != 0)
            done += 1
            _log(f"{message}  ({done}/{len(jobs)})")
    _log(f"finished: failures={failures}/{len(jobs)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
