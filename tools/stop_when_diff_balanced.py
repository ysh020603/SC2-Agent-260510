#!/usr/bin/env python3
"""Stop a running OLD-6 sweep when difficulty counts become balanced.

Default target: max(diff counts) - min(diff counts) <= --max-gap (default 0),
i.e. veryeasy/medium/hard counts equal among completed valid jobs.

Does NOT touch other batches. Kimi / other sweeps continue.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from run_bo_list_strategy_sweep import is_job_completed  # noqa: E402
from run_kimi_nothink_strategy_sweep import _build_jobs  # noqa: E402


DIFFS = ("veryeasy", "medium", "hard")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    print(f"[{_now()}] {msg}", flush=True)


def completed_diff_counts(batch: str) -> Counter:
    jobs = _build_jobs(
        "banshees,battle_cruisers,bio,cyclones,marine_rush,two_base_tanks".split(","),
        ["KairosJunctionLE"],
        "protoss,terran,zerg".split(","),
        list(DIFFS),
        5,
    )
    c: Counter = Counter()
    for j in jobs:
        if is_job_completed(batch, j):
            c[j.enemy_difficulty] += 1
    return c


def pids_for_batch(batch: str) -> List[int]:
    out = subprocess.check_output(["ps", "-eo", "pid=,args="], text=True)
    pids: List[int] = []
    needles = [
        f"run_kimi_nothink_strategy_sweep.py --batch-name {batch}",
        f"run_experiment.py --batch-name {batch} ",
    ]
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        pid_s, _, args = line.partition(" ")
        try:
            pid = int(pid_s)
        except ValueError:
            continue
        if any(n in args for n in needles):
            pids.append(pid)
    return sorted(set(pids))


def stop_batch(batch: str, session: Optional[str]) -> None:
    pids = pids_for_batch(batch)
    log(f"Stopping batch={batch} pids={pids}")
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    time.sleep(2)
    # force leftovers
    for pid in pids_for_batch(batch):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if session:
        subprocess.run(
            ["tmux", "kill-session", "-t", session],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        log(f"Killed tmux session {session}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--batch-name",
        default="ds_flash_think_order_exec32b_6old_macro_r5",
    )
    ap.add_argument("--tmux-session", default="old6_ds_flash_think_exec32b")
    ap.add_argument("--interval", type=float, default=60.0)
    ap.add_argument(
        "--max-gap",
        type=int,
        default=0,
        help="Stop when max(diff)-min(diff) <= this (0 = equal counts).",
    )
    ap.add_argument(
        "--min-per-diff",
        type=int,
        default=52,
        help="Also require each difficulty >= this before stopping.",
    )
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    log(
        f"Watch balance stop: batch={args.batch_name} max_gap={args.max_gap} "
        f"min_per_diff={args.min_per_diff} interval={args.interval}s"
    )
    while True:
        c = completed_diff_counts(args.batch_name)
        vals = [c.get(d, 0) for d in DIFFS]
        gap = max(vals) - min(vals) if vals else 0
        n = sum(vals)
        ready = gap <= args.max_gap and min(vals) >= args.min_per_diff
        log(
            f"{'READY' if ready else 'WAIT'} n={n} "
            f"VE={c.get('veryeasy',0)} Med={c.get('medium',0)} Hard={c.get('hard',0)} "
            f"gap={gap}"
        )
        if ready:
            if args.dry_run:
                log("[dry-run] would stop now")
                return 0
            stop_batch(args.batch_name, args.tmux_session or None)
            c2 = completed_diff_counts(args.batch_name)
            log(
                f"Stopped. final VE={c2.get('veryeasy',0)} "
                f"Med={c2.get('medium',0)} Hard={c2.get('hard',0)}"
            )
            return 0
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
