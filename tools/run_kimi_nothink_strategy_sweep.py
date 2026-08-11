"""Strategy sweep with configurable models, difficulties, and concurrency.

Runs every combination of strategy x map x enemy race x difficulty x repeat,
using tools/run_experiment.py for each match.
"""

from __future__ import annotations

import argparse
import fcntl
import os
import subprocess
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from run_bo_list_strategy_sweep import is_job_completed

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAX_ATTEMPTS = 3
_PAUSE_LOG_LOCK = threading.Lock()
_PAUSE_ANNOUNCED = False

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
    parser.add_argument(
        "--index-base",
        type=int,
        default=0,
        help="Add this offset to every job.index / --run-index (e.g. append veryhard as run540+).",
    )
    parser.add_argument(
        "--skip-completed",
        action="store_true",
        help="Skip jobs that already have a valid record under game_records/<batch-name>/.",
    )
    parser.add_argument(
        "--exclude-difficulties",
        default="",
        help=(
            "Comma-separated difficulties to drop after job indexing "
            "(keeps run-index stable vs full difficulty list). E.g. veryhard."
        ),
    )
    parser.add_argument(
        "--job-stride",
        type=int,
        default=1,
        help="Keep only jobs where index %% job-stride == job-offset (shard across replica workers).",
    )
    parser.add_argument(
        "--job-offset",
        type=int,
        default=0,
        help="Shard residue for --job-stride (e.g. offset 0 and 1 with stride 2).",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=DEFAULT_MAX_ATTEMPTS,
        help="Retry a job when the process exits without a valid result record.",
    )
    parser.add_argument(
        "--pause-hhmm-windows",
        default="",
        help=(
            "Comma-separated HH:MM-HH:MM local windows where NEW jobs must not start "
            "(in-flight games may finish). Example: 09:00-12:00,14:00-18:00"
        ),
    )
    parser.add_argument(
        "--pause-timezone",
        default="Asia/Shanghai",
        help="IANA timezone for --pause-hhmm-windows (default: Asia/Shanghai / Beijing).",
    )
    parser.add_argument(
        "--schedule-balance",
        default="",
        help=(
            "Reorder pending jobs to keep counts balanced while running. "
            "Comma-separated priorities among: difficulty,race. "
            "Example: difficulty,race (difficulty first)."
        ),
    )
    return parser.parse_args(argv)


def _parse_schedule_balance(spec: str) -> List[str]:
    allowed = {"difficulty", "race"}
    keys: List[str] = []
    for part in (spec or "").split(","):
        key = part.strip().lower()
        if not key:
            continue
        if key not in allowed:
            raise SystemExit(
                f"Invalid --schedule-balance key {part!r}; "
                f"allowed: {', '.join(sorted(allowed))}"
            )
        if key not in keys:
            keys.append(key)
    return keys


def _reorder_jobs_for_balance(
    pending: Sequence[MatchJob],
    *,
    completed_diff: Dict[str, int],
    completed_race: Dict[str, int],
    priorities: Sequence[str],
) -> List[MatchJob]:
    """Greedy schedule: always emit the job that most improves running balance."""
    if not priorities:
        return list(pending)
    remaining = list(pending)
    out: List[MatchJob] = []
    counts_d = Counter(completed_diff)
    counts_r = Counter(completed_race)

    while remaining:
        def sort_key(job: MatchJob) -> Tuple:
            key_parts = []
            for p in priorities:
                if p == "difficulty":
                    key_parts.append(counts_d[job.enemy_difficulty])
                elif p == "race":
                    key_parts.append(counts_r[job.enemy_race])
            key_parts.append(job.index)
            return tuple(key_parts)

        best = min(remaining, key=sort_key)
        remaining.remove(best)
        out.append(best)
        counts_d[best.enemy_difficulty] += 1
        counts_r[best.enemy_race] += 1
    return out


def _parse_hhmm(value: str) -> dt_time:
    hh, mm = value.strip().split(":")
    return dt_time(hour=int(hh), minute=int(mm))


def _parse_pause_windows(spec: str) -> List[Tuple[dt_time, dt_time]]:
    windows: List[Tuple[dt_time, dt_time]] = []
    for part in (spec or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" not in part:
            raise SystemExit(f"Invalid pause window (want HH:MM-HH:MM): {part!r}")
        start_s, end_s = part.split("-", 1)
        start, end = _parse_hhmm(start_s), _parse_hhmm(end_s)
        if start == end:
            raise SystemExit(f"Invalid pause window (empty range): {part!r}")
        windows.append((start, end))
    return windows


def _in_pause_window(now_local: datetime, windows: Sequence[Tuple[dt_time, dt_time]]) -> bool:
    cur = now_local.time().replace(tzinfo=None, microsecond=0)
    for start, end in windows:
        if start < end:
            if start <= cur < end:
                return True
        else:
            # overnight window, e.g. 22:00-06:00
            if cur >= start or cur < end:
                return True
    return False


def _seconds_until_pause_end(now_local: datetime, windows: Sequence[Tuple[dt_time, dt_time]]) -> float:
    """Seconds until the current pause window ends; 0 if not paused."""
    from datetime import timedelta

    if not _in_pause_window(now_local, windows):
        return 0.0
    cur = now_local.time().replace(tzinfo=None, microsecond=0)
    for start, end in windows:
        if start < end:
            active = start <= cur < end
        else:
            active = cur >= start or cur < end
        if not active:
            continue
        end_dt = now_local.replace(hour=end.hour, minute=end.minute, second=0, microsecond=0)
        if start >= end and cur >= start:
            end_dt = end_dt + timedelta(days=1)
        return max(1.0, (end_dt - now_local).total_seconds())
    return 60.0


def _wait_out_pause_windows(
    windows: Sequence[Tuple[dt_time, dt_time]],
    tz_name: str,
    job_label: str = "",
) -> None:
    global _PAUSE_ANNOUNCED
    if not windows:
        return
    tz = ZoneInfo(tz_name)
    local_announced = False
    while True:
        now_local = datetime.now(tz)
        if not _in_pause_window(now_local, windows):
            if local_announced:
                with _PAUSE_LOG_LOCK:
                    if _PAUSE_ANNOUNCED:
                        print(
                            f"[pause] resume off-peak at "
                            f"{now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}",
                            flush=True,
                        )
                        _PAUSE_ANNOUNCED = False
            return
        remain = _seconds_until_pause_end(now_local, windows)
        wait_s = min(max(remain, 5.0), 300.0)  # poll every 5s..5min
        if not local_announced:
            with _PAUSE_LOG_LOCK:
                if not _PAUSE_ANNOUNCED:
                    print(
                        f"[pause] peak window "
                        f"{now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}; "
                        f"no new jobs for ~{remain/60:.0f}m "
                        f"(tz={tz_name})",
                        flush=True,
                    )
                    _PAUSE_ANNOUNCED = True
            local_announced = True
        time.sleep(wait_s)


def _job_lock_path(batch_name: str, run_index: int) -> Path:
    lock_dir = ROOT / "game_records" / "_batch_locks" / batch_name
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / f"run{run_index}.lock"


def _try_acquire_job_lock(lock_fh) -> bool:
    try:
        fcntl.flock(lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


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
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    pause_windows: Optional[Sequence[Tuple[dt_time, dt_time]]] = None,
    pause_timezone: str = "Asia/Shanghai",
) -> tuple[MatchJob, int, str]:
    base_summary = (
        f"idx={job.index} strategy={job.strategy} map={job.map_name} "
        f"vs={job.enemy_race}/{job.enemy_difficulty} rep={job.repeat}"
    )

    # Re-check at worker start: another shard/session may have finished this job.
    if is_job_completed(batch_name, job):
        return job, 0, f"{base_summary} exit=0 skipped=already_completed"

    # Wait before lock so peak hours do not pin job locks / concurrency slots forever.
    _wait_out_pause_windows(
        pause_windows or (),
        pause_timezone,
        job_label=f"idx={job.index}",
    )

    lock_path = _job_lock_path(batch_name, job.index)
    with lock_path.open("a+", encoding="utf-8") as lock_fh:
        if not _try_acquire_job_lock(lock_fh):
            return job, 0, f"{base_summary} exit=0 skipped=locked_by_other_worker"

        if is_job_completed(batch_name, job):
            return job, 0, f"{base_summary} exit=0 skipped=already_completed"

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

        attempts = max(1, int(max_attempts))
        last_code = 1
        for attempt in range(1, attempts + 1):
            if is_job_completed(batch_name, job):
                return job, 0, f"{base_summary} exit=0 skipped=already_completed"

            mode = "w" if attempt == 1 else "a"
            with log_file.open(mode, encoding="utf-8") as fh:
                if attempt > 1:
                    fh.write(f"\n\n===== RETRY attempt={attempt}/{attempts} =====\n")
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
                last_code = proc.returncode
                fh.write(f"\n[sweep] attempt={attempt}/{attempts} exit={last_code}\n")
                fh.flush()

            if is_job_completed(batch_name, job):
                return job, 0, f"{base_summary} exit={last_code} attempts={attempt}"

            # Process claimed success but left no valid record — treat as failure.
            if last_code == 0:
                last_code = 2

            if attempt < attempts:
                time.sleep(min(15 * attempt, 60))

        return job, last_code, f"{base_summary} exit={last_code} attempts={attempts} no_valid_result"


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    difficulties = [d.strip() for d in args.difficulties.split(",") if d.strip()]
    enemy_races = [r.strip() for r in args.enemy_races.split(",") if r.strip()]
    maps = [m.strip() for m in args.maps.split(",") if m.strip()]
    jobs = _build_jobs(strategies, maps, enemy_races, difficulties, args.repeats)
    if args.index_base:
        jobs = [
            MatchJob(
                index=j.index + args.index_base,
                strategy=j.strategy,
                map_name=j.map_name,
                enemy_race=j.enemy_race,
                enemy_difficulty=j.enemy_difficulty,
                repeat=j.repeat,
            )
            for j in jobs
        ]
    jobs = [j for j in jobs if j.index >= args.start_index]
    exclude_diffs = {
        d.strip().lower()
        for d in (args.exclude_difficulties or "").split(",")
        if d.strip()
    }
    if exclude_diffs:
        before = len(jobs)
        jobs = [j for j in jobs if j.enemy_difficulty.lower() not in exclude_diffs]
        print(
            f"Exclude difficulties: {sorted(exclude_diffs)} "
            f"-> {len(jobs)}/{before}"
        )
    if args.job_stride < 1:
        raise SystemExit("--job-stride must be >= 1")
    if not (0 <= args.job_offset < args.job_stride):
        raise SystemExit("--job-offset must satisfy 0 <= offset < job-stride")
    if args.job_stride > 1:
        before = len(jobs)
        jobs = [j for j in jobs if j.index % args.job_stride == args.job_offset]
        print(
            f"Job shard: stride={args.job_stride} offset={args.job_offset} "
            f"-> {len(jobs)}/{before}"
        )
    balance_keys = _parse_schedule_balance(args.schedule_balance)
    completed_diff: Counter = Counter()
    completed_race: Counter = Counter()
    if args.skip_completed or balance_keys:
        for job in jobs:
            if is_job_completed(args.batch_name, job):
                completed_diff[job.enemy_difficulty] += 1
                completed_race[job.enemy_race] += 1
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
        if skipped:
            print(
                "Completed so far: "
                f"diff={dict(completed_diff)} race={dict(completed_race)}"
            )

    if balance_keys and jobs:
        before_preview = [
            (j.enemy_difficulty, j.enemy_race, j.index) for j in jobs[:12]
        ]
        jobs = _reorder_jobs_for_balance(
            jobs,
            completed_diff=completed_diff,
            completed_race=completed_race,
            priorities=balance_keys,
        )
        after_preview = [
            (j.enemy_difficulty, j.enemy_race, j.index) for j in jobs[:12]
        ]
        print(f"Schedule balance: {','.join(balance_keys)}")
        print(f"  next(before)={before_preview}")
        print(f"  next(after) ={after_preview}")

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
    print(f"Max attempts/job: {args.max_attempts}")
    print(f"Logs: {log_dir}")
    pause_windows = _parse_pause_windows(args.pause_hhmm_windows)
    if pause_windows:
        win_s = ", ".join(
            f"{a.strftime('%H:%M')}-{b.strftime('%H:%M')}" for a, b in pause_windows
        )
        print(f"Pause new jobs: {win_s} ({args.pause_timezone})")
        # If we start during peak, block the main thread first so logs are clear.
        _wait_out_pause_windows(pause_windows, args.pause_timezone, job_label="startup")

    if args.dry_run:
        for job in jobs[:5]:
            print(f"  [{job.index}] {job.strategy} @ {job.map_name} vs {job.enemy_race}/{job.enemy_difficulty} x{job.repeat}")
        if len(jobs) > 5:
            print(f"  ... and {len(jobs) - 5} more")
        return 0

    if not jobs:
        print("No pending jobs.")
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
                args.max_attempts,
                pause_windows,
                args.pause_timezone,
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
