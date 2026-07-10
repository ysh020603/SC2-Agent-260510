"""Strategy sweep with configurable models, difficulties, and concurrency.

Runs every combination of strategy x map x enemy race x difficulty x repeat,
using tools/run_experiment.py for each match.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]

STRATEGIES = [
    "bio",
    "safe_tvt_raven",
    "three_rax_stim",
    "two_base_tanks",
    "tank_thor_mech",
    "battle_cruisers",
]

MAPS = [
    "KairosJunctionLE",
    "AutomatonLE",
    "AbyssalReefLE",
]

ENEMY_RACES = ["protoss", "terran", "zerg"]

DEFAULT_DIFFICULTIES = ["medium", "mediumhard", "hard", "harder", "veryhard"]

DEFAULT_NAMING_MODEL = "Kimi-k2.5"
DEFAULT_ORDERING_MODEL = "Kimi-k2.5"
DEFAULT_EXECUTOR_MODEL = "Kimi-k2.5"
DEFAULT_DECISION_MODE = "three-stage"
DEFAULT_ENEMY_BUILD = "random"
DEFAULT_BATCH_NAME = "kimi_nothink_v7_strategies"
DEFAULT_GAME_TIME_LIMIT = 20 * 60
DEFAULT_REPEATS = 2
DEFAULT_CONCURRENCY = 3


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
    """Schedule map/race/difficulty first so every matchup cycles through all strategies."""
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
        description="Run Kimi non-thinking strategy sweep with concurrency.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--batch-name", default=DEFAULT_BATCH_NAME)
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--game-time-limit", type=int, default=DEFAULT_GAME_TIME_LIMIT)
    parser.add_argument("--naming-model", default=DEFAULT_NAMING_MODEL)
    parser.add_argument("--ordering-model", default=DEFAULT_ORDERING_MODEL)
    parser.add_argument("--executor-model", default=DEFAULT_EXECUTOR_MODEL)
    parser.add_argument(
        "--decision-mode",
        choices=("three-stage", "two-stage"),
        default=DEFAULT_DECISION_MODE,
    )
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
        help="Comma-separated strategy folder names under SKILL/<race>/.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--start-index",
        type=int,
        default=0,
        help="Skip jobs with index < start-index (resume support).",
    )
    return parser.parse_args(argv)


def _run_one(
    job: MatchJob,
    batch_name: str,
    game_time_limit: int,
    log_dir: Path,
    naming_model: str,
    ordering_model: str,
    executor_model: str,
    decision_mode: str,
    enemy_build: str,
) -> tuple[MatchJob, int, str]:
    cmd = [
        sys.executable,
        str(ROOT / "tools" / "run_experiment.py"),
        "--strategy",
        job.strategy,
        "--batch-name",
        batch_name,
        "--match-prefix",
        job.match_prefix,
        "--map-name",
        job.map_name,
        "--enemy-race",
        job.enemy_race,
        "--enemy-difficulty",
        job.enemy_difficulty,
        "--enemy-build",
        enemy_build,
        "--naming-model",
        naming_model,
        "--ordering-model",
        ordering_model,
        "--executor-model",
        executor_model,
        "--decision-mode",
        decision_mode,
        "--no-supply-managed",
        "--game-time-limit",
        str(game_time_limit),
        "--run-index",
        str(job.index),
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

    log_dir = ROOT / "game_records" / "_batch_logs" / args.batch_name
    log_dir.mkdir(parents=True, exist_ok=True)

    print(f"Batch: {args.batch_name}")
    print(
        f"Models: naming={args.naming_model}, ordering={args.ordering_model}, "
        f"executor={args.executor_model}"
    )
    print(f"Decision mode: {args.decision_mode}")
    print(f"Difficulties: {difficulties}")
    print(f"Enemy races: {enemy_races}")
    print(f"Enemy build: {args.enemy_build}")
    print(f"Maps: {maps}")
    print(f"Jobs: {len(jobs)} (concurrency={args.concurrency}, repeats={args.repeats})")
    print(f"Logs: {log_dir}")

    if args.dry_run:
        for job in jobs[:5]:
            print(f"  [{job.index}] {job.strategy} @ {job.map_name} vs {job.enemy_race}/{job.enemy_difficulty} x{job.repeat}")
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
                args.naming_model,
                args.ordering_model,
                args.executor_model,
                args.decision_mode,
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
