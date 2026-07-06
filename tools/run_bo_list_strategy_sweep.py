"""BO-list strategy sweep with configurable executor model and concurrency.

Runs every combination of strategy x map x enemy race x difficulty x repeat,
using run_vs_ai.play_vs_ai with --bo-list (bypasses Naming/Ordering LLM).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]

STRATEGIES = [
    "bio",
    "safe_tvt_raven",
    "three_rax_stim",
    "two_base_tanks",
    "tank_thor_mech",
    "battle_cruisers",
    "marine_rush",
    "rusty",
    "banshees",
    "raven_liberator_tank",
]

MAPS = ["KairosJunctionLE"]
ENEMY_RACES = ["protoss", "terran", "zerg"]
DEFAULT_DIFFICULTIES = ["veryeasy", "medium", "hard"]
DEFAULT_EXECUTOR_MODEL = "Qwen35-27b"
DEFAULT_ENEMY_BUILD = "macro"
DEFAULT_BATCH_NAME = "bo_list_exec_sweep"
DEFAULT_GAME_TIME_LIMIT = 20 * 60
DEFAULT_REPEATS = 5
DEFAULT_CONCURRENCY = 5


@dataclass(frozen=True)
class MatchJob:
    index: int
    strategy: str
    map_name: str
    enemy_race: str
    enemy_difficulty: str
    repeat: int

    @property
    def match_prefix(self) -> str:
        strat = self.strategy.replace("_", "")[:10]
        mp = self.map_name.replace("LE", "")[:6]
        return f"{strat}_{mp}_{self.enemy_race[:1]}{self.enemy_difficulty[:2]}_r{self.repeat}"


def _build_jobs(
    strategies: Sequence[str],
    maps: Sequence[str],
    races: Sequence[str],
    difficulties: Sequence[str],
    repeats: int,
) -> List[MatchJob]:
    jobs: List[MatchJob] = []
    idx = 0
    for map_name in maps:
        for enemy_race in races:
            for enemy_difficulty in difficulties:
                for repeat in range(1, repeats + 1):
                    for strategy in strategies:
                        jobs.append(
                            MatchJob(
                                index=idx,
                                strategy=strategy,
                                map_name=map_name,
                                enemy_race=enemy_race,
                                enemy_difficulty=enemy_difficulty,
                                repeat=repeat,
                            )
                        )
                        idx += 1
    return jobs


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run BO-list strategy sweep with concurrency.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--game-time-limit", type=int, default=DEFAULT_GAME_TIME_LIMIT)
    parser.add_argument("--executor-model", default=DEFAULT_EXECUTOR_MODEL)
    parser.add_argument(
        "--difficulties",
        default=",".join(DEFAULT_DIFFICULTIES),
        help="Comma-separated enemy difficulties.",
    )
    parser.add_argument(
        "--enemy-races",
        default=",".join(ENEMY_RACES),
        help="Comma-separated enemy races.",
    )
    parser.add_argument("--enemy-build", default=DEFAULT_ENEMY_BUILD)
    parser.add_argument(
        "--maps",
        default=",".join(MAPS),
        help="Comma-separated map names.",
    )
    parser.add_argument(
        "--strategies",
        default=",".join(STRATEGIES),
        help="Comma-separated BO-list strategy folder names under BO_list/<race>/.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Skip jobs with index < start-index (resume support).",
    )
    parser.add_argument(
        "--skip-completed",
        action="store_true",
        help="Skip jobs that already have a valid record under game_records/<batch-name>/.",
    )
    return parser.parse_args(argv)


def _result_json_paths(record_dir: Path) -> List[Path]:
    return [
        path
        for path in record_dir.glob("*.json")
        if not path.name.endswith(".llm_calls.json")
    ]


def is_valid_record_dir(record_dir: Path) -> bool:
    """Return True when a match folder contains a usable result JSON."""
    if not record_dir.is_dir():
        return False
    for path in _result_json_paths(record_dir):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and ("metadata" in data or "interactions" in data):
            return True
    return False


def find_record_dir(batch_name: str, run_index: int) -> Optional[Path]:
    batch_dir = ROOT / "game_records" / batch_name
    if not batch_dir.is_dir():
        return None
    suffix = f"_run{run_index}"
    matches = sorted(
        path
        for path in batch_dir.iterdir()
        if path.is_dir() and path.name.endswith(suffix)
    )
    return matches[-1] if matches else None


def is_job_completed(batch_name: str, job: MatchJob) -> bool:
    record_dir = find_record_dir(batch_name, job.index)
    return record_dir is not None and is_valid_record_dir(record_dir)


def cleanup_invalid_batch_records(
    batch_name: str,
    *,
    migrate_from: Optional[Sequence[str]] = None,
) -> tuple[int, int, int]:
    """Delete invalid record dirs; optionally migrate valid ones from older batches."""
    batch_dir = ROOT / "game_records" / batch_name
    batch_dir.mkdir(parents=True, exist_ok=True)

    migrated = 0
    for source_name in migrate_from or ():
        source_dir = ROOT / "game_records" / source_name
        if not source_dir.is_dir():
            continue
        for record_dir in sorted(source_dir.iterdir()):
            if not record_dir.is_dir() or not record_dir.name.startswith("2026"):
                continue
            target_dir = batch_dir / record_dir.name
            if is_valid_record_dir(record_dir):
                if target_dir.exists():
                    shutil.rmtree(record_dir)
                else:
                    shutil.move(str(record_dir), str(target_dir))
                    migrated += 1
            else:
                shutil.rmtree(record_dir)

    deleted = 0
    kept = 0
    for record_dir in sorted(batch_dir.iterdir()):
        if not record_dir.is_dir() or not record_dir.name.startswith("2026"):
            continue
        if is_valid_record_dir(record_dir):
            kept += 1
            continue
        shutil.rmtree(record_dir)
        deleted += 1
    return migrated, kept, deleted


def _run_one(
    job: MatchJob,
    batch_name: str,
    game_time_limit: int,
    log_dir: Path,
    executor_model: str,
    enemy_build: str,
) -> tuple[MatchJob, int, str]:
    cmd = [
        sys.executable,
        "-c",
        (
            "import os, sys; "
            f"sys.path.insert(0, {str(ROOT)!r}); "
            "import run_vs_ai; "
            f"os.environ['SC2_GAME_TIME_LIMIT'] = {str(game_time_limit)!r}; "
            "run_vs_ai.play_vs_ai("
            f"bo_list={job.strategy!r}, "
            f"batch_name={batch_name!r}, "
            f"map_name={job.map_name!r}, "
            f"enemy_race={job.enemy_race!r}, "
            f"enemy_difficulty={job.enemy_difficulty!r}, "
            f"enemy_build={enemy_build!r}, "
            f"executor_model={executor_model!r}, "
            f"run_index={job.index}, "
            "skip_version_update=True"
            ")"
        ),
    ]

    log_file = log_dir / f"job_{job.index:04d}_{job.match_prefix}.log"
    env = os.environ.copy()
    env.setdefault("SC2PATH", "/data2/SC2/StarCraftII/")
    env["SC2_GAME_TIME_LIMIT"] = str(game_time_limit)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    with log_file.open("w", encoding="utf-8") as fh:
        fh.write("CMD: " + " ".join(cmd) + "\n\n")
        fh.flush()
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            stdout=fh,
            stderr=subprocess.STDOUT,
            check=False,
        )
    summary = (
        f"idx={job.index} strategy={job.strategy} map={job.map_name} "
        f"vs={job.enemy_race}/{job.enemy_difficulty} rep={job.repeat} exit={proc.returncode}"
    )
    return job, proc.returncode, summary


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    difficulties = [d.strip() for d in args.difficulties.split(",") if d.strip()]
    enemy_races = [r.strip() for r in args.enemy_races.split(",") if r.strip()]
    maps = [m.strip() for m in args.maps.split(",") if m.strip()]
    jobs = _build_jobs(strategies, maps, enemy_races, difficulties, args.repeats)
    jobs = [j for j in jobs if j.index >= args.start_index]
    if args.skip_completed:
        pending = []
        skipped = 0
        for job in jobs:
            if is_job_completed(args.batch_name, job):
                skipped += 1
                continue
            pending.append(job)
        jobs = pending
        print(f"Skip completed: {skipped}")

    log_dir = ROOT / "game_records" / "_batch_logs" / args.batch_name
    log_dir.mkdir(parents=True, exist_ok=True)

    print(f"Batch: {args.batch_name}")
    print(f"Mode: BO-list (executor only) | executor={args.executor_model}")
    print(f"Difficulties: {difficulties}")
    print(f"Enemy races: {enemy_races}")
    print(f"Enemy build: {args.enemy_build}")
    print(f"Maps: {maps}")
    print(f"Jobs: {len(jobs)} (concurrency={args.concurrency}, repeats={args.repeats})")
    print(f"Logs: {log_dir}")

    if args.dry_run:
        for job in jobs[:5]:
            print(
                f"  [{job.index}] bo-list={job.strategy} @ {job.map_name} "
                f"vs {job.enemy_race}/{job.enemy_difficulty} x{job.repeat}"
            )
        if len(jobs) > 5:
            print(f"  ... and {len(jobs) - 5} more")
        return 0

    started = time.time()
    failures = 0
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = {
            pool.submit(
                _run_one,
                job,
                args.batch_name,
                args.game_time_limit,
                log_dir,
                args.executor_model,
                args.enemy_build,
            ): job
            for job in jobs
        }
        done = 0
        for fut in as_completed(futures):
            job, code, summary = fut.result()
            done += 1
            if code != 0:
                failures += 1
            print(f"[{done}/{len(jobs)}] {summary}", flush=True)

    elapsed = time.time() - started
    print(f"Done in {elapsed / 60:.1f} min. failures={failures}/{len(jobs)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
