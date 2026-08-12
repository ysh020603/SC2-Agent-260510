"""Launch 30-way human-skill evaluation with isolated three-match runners.

The lifecycle-safe unit remains one runner with three SC2 children.  Ten
independent runners provide the requested total concurrency of 30 while
preserving process isolation, two-second launch staggering, natural child
exit, and serial retries.
"""

from __future__ import annotations

import argparse
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path("/home/wyq/miniconda3/bin/python")
SHARDS = tuple(f"{start}-{start + 2}" for start in range(0, 30, 3))


def main() -> int:
    parser = argparse.ArgumentParser()
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--method", default="")
    selection.add_argument(
        "--phase",
        choices=("full", "ablations", "all"),
        help="Use 'all' for the registered full/full-v2/full-v3/full-v4/full-v5 and ablation comparison.",
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--batch-prefix", required=True)
    parser.add_argument("--difficulty", default="mediumhard")
    parser.add_argument("--game-time-limit", type=int, default=1200)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--run-index-offset", type=int, default=0)
    parser.add_argument("--runner-launch-stagger", type=float, default=2.0)
    parser.add_argument("--protocol-response-timeout", type=float, default=90.0)
    parser.add_argument("--protocol-observation-timeout", type=float, default=120.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.repeats < 1 or args.run_index_offset < 0:
        raise ValueError("repeats must be positive and run-index-offset non-negative")
    active_shards = tuple(
        f"{args.run_index_offset + start}-{args.run_index_offset + start + 2}"
        for start in range(0, 30, 3)
    )

    method_count = 1 if args.method else {"full": 1, "ablations": 8, "all": 9}[args.phase]
    print(
        f"preflight shards={len(active_shards)} per_runner_concurrency=3 "
        f"total_concurrency=30 methods={method_count} expected_jobs={30 * method_count}",
        flush=True,
    )

    log_root = ROOT / "game_records" / "_human_skill_ablation" / args.batch_prefix
    log_root.mkdir(parents=True, exist_ok=True)

    def run_shard(shard_index: int, indices: str) -> tuple[int, int]:
        command = [
            str(PYTHON),
            "tools/run_human_skill_ablation_suite.py",
            "--model",
            args.model,
            "--batch-prefix",
            args.batch_prefix,
            "--difficulty",
            args.difficulty,
            "--game-time-limit",
            str(args.game_time_limit),
            "--max-attempts",
            str(args.max_attempts),
            "--repeats",
            str(args.repeats),
            "--run-indices",
            indices,
            "--concurrency",
            "3",
            "--retry-concurrency",
            "1",
            "--launch-stagger",
            "2.0",
            "--protocol-response-timeout",
            str(args.protocol_response_timeout),
            "--protocol-observation-timeout",
            str(args.protocol_observation_timeout),
            "--manifest-name",
            f"suite_manifest_offset{args.run_index_offset}_shard_{shard_index}.json",
        ]
        if args.method:
            command.extend(["--method", args.method])
        else:
            command.extend(["--phase", args.phase])
        log_path = log_root / f"reference_topology_offset{args.run_index_offset}_shard_{shard_index}.log"
        if args.dry_run:
            print(f"shard={shard_index} run_indices={indices} command={' '.join(command)}")
            return shard_index, 0
        with log_path.open("w", encoding="utf-8") as log:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        return shard_index, completed.returncode

    futures = {}
    with ThreadPoolExecutor(max_workers=len(SHARDS)) as pool:
        for shard_index, indices in enumerate(active_shards):
            if shard_index and args.runner_launch_stagger > 0:
                time.sleep(args.runner_launch_stagger)
            futures[pool.submit(run_shard, shard_index, indices)] = shard_index
        failures = []
        for future in as_completed(futures):
            shard_index, returncode = future.result()
            print(f"shard={shard_index} returncode={returncode}", flush=True)
            if returncode != 0:
                failures.append(shard_index)

    print(
        f"reference topology complete shards={len(active_shards)} total_concurrency=30 failures={failures}",
        flush=True,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
