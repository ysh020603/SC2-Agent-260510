"""Launch 15 human-skill matches with the stable reference-repo topology.

The known-good knowledge-repo matrix uses five independent sweep runners with
three SC2 children each.  This wrapper reproduces that process isolation and
two-second launch staggering while keeping one shared treatment batch.
"""

from __future__ import annotations

import argparse
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path("/home/wyq/miniconda3/bin/python")
SHARDS = ("0-2", "3-5", "6-8", "9-11", "12-14")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--batch-prefix", required=True)
    parser.add_argument("--difficulty", default="mediumhard")
    parser.add_argument("--game-time-limit", type=int, default=1200)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--runner-launch-stagger", type=float, default=2.0)
    parser.add_argument("--protocol-response-timeout", type=float, default=90.0)
    parser.add_argument("--protocol-observation-timeout", type=float, default=120.0)
    args = parser.parse_args()

    log_root = ROOT / "game_records" / "_human_skill_ablation" / args.batch_prefix
    log_root.mkdir(parents=True, exist_ok=True)

    def run_shard(shard_index: int, indices: str) -> tuple[int, int]:
        command = [
            str(PYTHON),
            "tools/run_human_skill_ablation_suite.py",
            "--method",
            args.method,
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
            "--indices",
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
            f"suite_manifest_shard_{shard_index}.json",
        ]
        log_path = log_root / f"reference_topology_shard_{shard_index}.log"
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
        for shard_index, indices in enumerate(SHARDS):
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
        f"reference topology complete shards={len(SHARDS)} failures={failures}",
        flush=True,
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
