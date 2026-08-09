"""Run the paired 15-condition readable-skill ablation suite.

The same conditions are reused for the full method and every ablation so that
method is the only intended treatment variable. Existing completed matches are
discovered from their trace artifacts, making an interrupted suite resumable.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path("/home/wyq/miniconda3/envs/SC2_0615/bin/python")

METHODS = {
    "full": "human-skill-full",
    "single_trace": "human-skill-single-trace",
    "flat_adaptive": "human-skill-flat-adaptive",
    "positive_only": "human-skill-positive-only",
}


@dataclass(frozen=True)
class Condition:
    index: int
    bot_race: str
    enemy_race: str
    skill_id: str
    enemy_build: str


CONDITIONS = (
    Condition(0, "protoss", "protoss", "PvP_O01", "macro"),
    Condition(1, "protoss", "terran", "PvT_O03", "timing"),
    Condition(2, "protoss", "zerg", "PvZ_O02", "rush"),
    Condition(3, "protoss", "terran", "PvT_O07", "power"),
    Condition(4, "protoss", "zerg", "PvZ_O05", "air"),
    Condition(5, "terran", "protoss", "TvP_O02", "timing"),
    Condition(6, "terran", "terran", "TvT_O03", "macro"),
    Condition(7, "terran", "zerg", "TvZ_O01", "rush"),
    Condition(8, "terran", "protoss", "TvP_O06", "power"),
    Condition(9, "terran", "zerg", "TvZ_O05", "air"),
    Condition(10, "zerg", "protoss", "ZvP_O01", "rush"),
    Condition(11, "zerg", "terran", "ZvT_O04", "timing"),
    Condition(12, "zerg", "zerg", "ZvZ_O04", "macro"),
    Condition(13, "zerg", "protoss", "ZvP_O06", "air"),
    Condition(14, "zerg", "terran", "ZvT_O05", "power"),
)


def _method_for_trace(trace: dict) -> str:
    decisions = trace.get("decisions") or []
    return str(decisions[0].get("skill_method") if decisions else "")


def record_has_watchdog(record_dir: Path) -> bool:
    for calls_path in record_dir.glob("*.llm_calls.json"):
        try:
            payload = json.loads(calls_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if any(
            item.get("event") == "sc2_protocol_watchdog_recovery"
            for item in (payload.get("calls") or [])
            if isinstance(item, dict)
        ):
            return True
    return False


def completed_skill_ids(batch_dir: Path) -> set[str]:
    completed: set[str] = set()
    if not batch_dir.exists():
        return completed
    for trace_path in batch_dir.glob("*/*.human_skill.json"):
        try:
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            match = json.loads((trace_path.parent / "match.json").read_text(encoding="utf-8"))
            decisions = trace.get("decisions") or []
            skill_id = str(decisions[0].get("skill_id") if decisions else "")
            if (
                skill_id
                and not record_has_watchdog(trace_path.parent)
                and match.get("metadata", {}).get("result") in {"Victory", "Defeat", "Tie"}
            ):
                completed.add(skill_id)
        except (OSError, ValueError, TypeError):
            continue
    return completed


def selected_methods(phase: str) -> Iterable[tuple[str, str]]:
    if phase == "full":
        return (("full", METHODS["full"]),)
    if phase == "ablations":
        return tuple((name, agent) for name, agent in METHODS.items() if name != "full")
    return tuple(METHODS.items())


def selected_indices(value: str) -> set[int]:
    result: set[int] = set()
    for part in value.split(","):
        token = part.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError(f"invalid descending index range: {token}")
            result.update(range(start, end + 1))
        else:
            result.add(int(token))
    valid = {item.index for item in CONDITIONS}
    if not result or not result <= valid:
        raise ValueError(f"indices must select from {sorted(valid)}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("full", "ablations", "all"), default="full")
    parser.add_argument("--difficulty", default="mediumhard")
    parser.add_argument("--map-name", default="KairosJunctionLE")
    parser.add_argument("--game-time-limit", type=int, default=1200)
    parser.add_argument("--decision-interval", type=float, default=60.0)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--wall-timeout", type=int, default=3000)
    parser.add_argument("--protocol-response-timeout", type=float, default=90.0)
    parser.add_argument("--ai-step-timeout", type=float, default=180.0)
    parser.add_argument("--launch-stagger", type=float, default=5.0)
    parser.add_argument("--batch-prefix", default="human_skill_ablation_1200_mediumhard_20260809")
    parser.add_argument("--manifest-name", default="suite_manifest.json")
    parser.add_argument("--model", default="DeepSeek-V4-flash")
    parser.add_argument("--indices", default="0-14")
    args = parser.parse_args()
    if args.concurrency < 1:
        raise ValueError("concurrency must be positive")
    if Path(args.manifest_name).name != args.manifest_name or not args.manifest_name.endswith(".json"):
        raise ValueError("manifest-name must be a plain .json file name")
    if (
        args.wall_timeout < 1
        or args.protocol_response_timeout <= 0
        or args.ai_step_timeout <= 0
        or args.launch_stagger < 0
    ):
        raise ValueError("timeouts must be positive")

    methods = list(selected_methods(args.phase))
    indices = selected_indices(args.indices)
    conditions = tuple(item for item in CONDITIONS if item.index in indices)
    state_root = ROOT / "game_records" / "_human_skill_ablation"
    log_root = state_root / args.batch_prefix
    log_root.mkdir(parents=True, exist_ok=True)
    manifest_path = log_root / args.manifest_name
    manifest_lock = threading.Lock()
    manifest = {
        "schema_version": 2,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "phase": args.phase,
        "difficulty": args.difficulty,
        "map_name": args.map_name,
        "game_time_limit": args.game_time_limit,
        "decision_interval": args.decision_interval,
        "wall_timeout": args.wall_timeout,
        "protocol_response_timeout": args.protocol_response_timeout,
        "ai_step_timeout": args.ai_step_timeout,
        "launch_stagger": args.launch_stagger,
        "model": args.model,
        "conditions": [asdict(item) for item in conditions],
        "methods": dict(methods),
        "jobs": [],
    }

    def save_manifest() -> None:
        temp = manifest_path.with_suffix(".tmp")
        temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(manifest_path)

    jobs: list[tuple[str, str, Condition, str, Path]] = []
    for method_name, agent in methods:
        batch_name = f"{args.batch_prefix}_{method_name}"
        done = completed_skill_ids(ROOT / "game_records" / batch_name)
        for condition in conditions:
            log_path = log_root / f"{method_name}_{condition.index:02d}_{condition.skill_id}.log"
            if condition.skill_id in done:
                manifest["jobs"].append(
                    {"method": method_name, "condition": asdict(condition), "status": "skipped_complete"}
                )
            else:
                jobs.append((method_name, agent, condition, batch_name, log_path))
    save_manifest()
    print(f"suite jobs pending={len(jobs)} concurrency={args.concurrency}", flush=True)
    launch_lock = threading.Lock()
    last_launch = [0.0]

    def run_job(job: tuple[str, str, Condition, str, Path]) -> dict:
        method_name, agent, condition, batch_name, log_path = job
        with launch_lock:
            delay = args.launch_stagger - (time.monotonic() - last_launch[0])
            if delay > 0:
                time.sleep(delay)
            last_launch[0] = time.monotonic()
        command = [
            "timeout",
            f"{args.wall_timeout}s",
            str(PYTHON),
            "run_vs_ai_human_skill.py",
            "--human-skill-agent",
            agent,
            "--force-human-skill",
            condition.skill_id,
            "--human-skill-root",
            "../SKILL_MINING_V2_READABLE",
            "--human-skill-api-config",
            "../API_config/config.json",
            "--decision-model",
            args.model,
            "--decision-interval",
            str(args.decision_interval),
            "--bot-race",
            condition.bot_race,
            "--enemy-race",
            condition.enemy_race,
            "--enemy-difficulty",
            args.difficulty,
            "--enemy-build",
            condition.enemy_build,
            "--map-name",
            args.map_name,
            "--output-base-dir",
            "./game_records",
            "--batch-name",
            batch_name,
            "--run-index",
            str(condition.index),
            "--skip-version-update",
        ]
        env = os.environ.copy()
        env.update(
            {
                "SC2PATH": "/data2/SC2/StarCraftII",
                "SC2_GAME_TIME_LIMIT": str(args.game_time_limit),
                "SC2_STARTUP_TIMEOUT": "240",
                "SC2_PROTOCOL_RESPONSE_TIMEOUT_SECONDS": str(args.protocol_response_timeout),
                "SC2_AI_STEP_TIMEOUT_SECONDS": str(args.ai_step_timeout),
                "PYTHONUNBUFFERED": "1",
            }
        )
        started = time.time()
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        artifact_complete = condition.skill_id in completed_skill_ids(ROOT / "game_records" / batch_name)
        return {
            "method": method_name,
            "agent": agent,
            "condition": asdict(condition),
            "batch_name": batch_name,
            "log_path": str(log_path.relative_to(ROOT)),
            "status": "complete" if process.returncode == 0 and artifact_complete else "failed",
            "returncode": process.returncode,
            "artifact_complete": artifact_complete,
            "wall_seconds": round(time.time() - started, 2),
        }

    failures = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(run_job, job): job for job in jobs}
        for future in as_completed(futures):
            result = future.result()
            failures += int(result["status"] != "complete")
            with manifest_lock:
                manifest["jobs"].append(result)
                save_manifest()
            print(
                f"[{len(manifest['jobs'])}/{len(jobs)}] {result['method']} "
                f"{result['condition']['skill_id']} {result['status']} "
                f"wall={result['wall_seconds']}s",
                flush=True,
            )
    manifest["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    manifest["failure_count"] = failures
    save_manifest()
    print(f"suite complete failures={failures} manifest={manifest_path}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
