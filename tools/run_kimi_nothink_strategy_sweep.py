"""Run a configurable strategy sweep through the single decision model."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from SC2_Agent.strategy_registry import enabled_strategy_names

DEFAULT_STRATEGIES = ["enabled"]
DEFAULT_MAPS = ["KairosJunctionLE", "AutomatonLE", "AbyssalReefLE"]
DEFAULT_BOT_RACES = ["terran", "protoss", "zerg"]
DEFAULT_ENEMY_RACES = ["protoss", "terran", "zerg"]
DEFAULT_DIFFICULTIES = ["medium", "mediumhard", "hard", "harder", "veryhard"]


class LaunchGate:
    """Keep concurrent SC2 clients from all initializing in the same instant."""

    def __init__(self, stagger_seconds: float) -> None:
        self.stagger_seconds = max(0.0, float(stagger_seconds))
        self._lock = threading.Lock()
        self._last_launch = 0.0

    def wait(self) -> None:
        with self._lock:
            remaining = self.stagger_seconds - (time.monotonic() - self._last_launch)
            if remaining > 0:
                time.sleep(remaining)
            self._last_launch = time.monotonic()


@dataclass(frozen=True)
class MatchJob:
    index: int
    bot_race: str
    strategy: str
    map_name: str
    enemy_race: str
    enemy_difficulty: str
    repeat: int

    @property
    def match_prefix(self) -> str:
        strategy = self.strategy.replace("_", "")[:10]
        map_part = self.map_name.replace("LE", "")[:6]
        return (
            f"{self.bot_race[:1]}_{strategy}_{map_part}_{self.enemy_race[:1]}"
            f"{self.enemy_difficulty[:2]}_r{self.repeat}"
        )


def _csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _jobs(
    strategies: Sequence[str],
    maps: Sequence[str],
    bot_races: Sequence[str],
    enemy_races: Sequence[str],
    difficulties: Sequence[str],
    repeats: int,
) -> List[MatchJob]:
    result: List[MatchJob] = []
    use_enabled = list(strategies) == ["enabled"]
    disabled = []
    for bot_race in bot_races:
        selected = (
            enabled_strategy_names(bot_race) if use_enabled else tuple(strategies)
        )
        enabled = set(enabled_strategy_names(bot_race))
        disabled.extend(
            f"{bot_race}/{strategy}"
            for strategy in selected
            if strategy not in enabled
        )
    if disabled:
        raise ValueError(
            "Strategies are missing or temporarily disabled for the selected "
            "bot race(s): " + ", ".join(disabled)
        )

    for bot_race in bot_races:
        race_strategies = (
            enabled_strategy_names(bot_race) if use_enabled else tuple(strategies)
        )
        for map_name in maps:
            for enemy_race in enemy_races:
                for difficulty in difficulties:
                    for repeat in range(1, repeats + 1):
                        for strategy in race_strategies:
                            result.append(
                                MatchJob(
                                    index=len(result),
                                    bot_race=bot_race,
                                    strategy=strategy,
                                    map_name=map_name,
                                    enemy_race=enemy_race,
                                    enemy_difficulty=difficulty,
                                    repeat=repeat,
                                )
                        )
    return result


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


def _completed(batch_name: str, run_index: int) -> bool:
    root = ROOT / "game_records" / batch_name
    if not root.is_dir():
        return False
    suffix = f"_run{run_index}"
    return any(
        path.name.endswith(suffix) and _valid_record_dir(path)
        for path in root.iterdir()
    )


def _child_environment(startup_timeout: float = 180.0) -> dict[str, str]:
    env = os.environ.copy()
    # Linux evaluation hosts use this conventional install path.  Windows
    # must let python-sc2 discover the registry/default installation; injecting
    # a POSIX path there makes every child fail before SC2 starts.
    if os.name != "nt":
        env.setdefault("SC2PATH", "/data2/SC2/StarCraftII/")
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env["SC2_STARTUP_TIMEOUT"] = str(max(1.0, float(startup_timeout)))
    return env


def _run_one(
    job: MatchJob,
    *,
    batch_name: str,
    model: str,
    subagent_model: str,
    decision_agent_mode: str,
    decision_interval: float,
    enemy_build: str,
    game_time_limit: int,
    log_dir: Path,
    max_attempts: int,
    launch_gate: LaunchGate,
    startup_timeout: float,
) -> tuple[int, str]:
    if _completed(batch_name, job.index):
        return 0, f"[{job.index}] skipped: already completed"
    command = [
        sys.executable,
        str(ROOT / "tools" / "run_experiment.py"),
        "--strategy",
        job.strategy,
        "--bot-race",
        job.bot_race,
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
        "--decision-model",
        model,
        "--data-subagent-model",
        subagent_model,
        "--decision-agent-mode",
        decision_agent_mode,
        "--decision-interval",
        str(decision_interval),
        "--game-time-limit",
        str(game_time_limit),
        "--run-index",
        str(job.index),
    ]
    env = _child_environment(startup_timeout)
    log_path = log_dir / f"job_{job.index:04d}_{job.match_prefix}.log"
    exit_code = 1
    for attempt in range(1, max(1, max_attempts) + 1):
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n===== attempt {attempt} =====\n")
            log.write("CMD: " + " ".join(command) + "\n")
            log.flush()
            launch_gate.wait()
            print(
                f"[{job.index}] launching attempt {attempt}: "
                f"{job.bot_race}/{job.strategy} vs "
                f"{job.enemy_race}/{job.enemy_difficulty}",
                flush=True,
            )
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
            exit_code = result.returncode
        if _completed(batch_name, job.index):
            return 0, f"[{job.index}] completed on attempt {attempt}"
        if attempt < max_attempts:
            time.sleep(min(attempt * 10, 30))
    return exit_code or 2, f"[{job.index}] failed without a valid record"


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--batch-name", default="kimi_nothink_summary_queue")
    parser.add_argument("--decision-model", default="Kimi-k2.5")
    parser.add_argument("--data-subagent-model", default="Kimi-k2.5")
    parser.add_argument(
        "--decision-agent-mode",
        choices=("data-v2.3", "data-v2.3-no-knowledge", "data-v2.2-v2-no-knowledge", "data-v2.2-v2", "data-v2.2", "naive"),
        default="data-v2.2",
    )
    parser.add_argument("--decision-interval", type=float, default=60.0)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--game-time-limit", type=int, default=1200)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument(
        "--launch-stagger-seconds",
        type=float,
        default=2.0,
        help="Minimum wall-clock gap between concurrent SC2 client launches.",
    )
    parser.add_argument(
        "--startup-timeout",
        type=float,
        default=180.0,
        help="Seconds allowed for an SC2 client to publish its websocket.",
    )
    parser.add_argument("--enemy-build", default="random")
    parser.add_argument("--strategies", default=",".join(DEFAULT_STRATEGIES))
    parser.add_argument("--maps", default=",".join(DEFAULT_MAPS))
    parser.add_argument("--bot-races", default=",".join(DEFAULT_BOT_RACES))
    parser.add_argument("--enemy-races", default=",".join(DEFAULT_ENEMY_RACES))
    parser.add_argument("--difficulties", default=",".join(DEFAULT_DIFFICULTIES))
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    jobs = _jobs(
        _csv(args.strategies),
        _csv(args.maps),
        _csv(args.bot_races),
        _csv(args.enemy_races),
        _csv(args.difficulties),
        args.repeats,
    )
    jobs = [job for job in jobs if job.index >= args.start_index]
    print(
        f"main_model={args.decision_model} subagent_model={args.data_subagent_model} "
        f"mode={args.decision_agent_mode} "
        f"interval={args.decision_interval:g}s "
        f"jobs={len(jobs)} concurrency={args.concurrency}"
    )
    if args.dry_run:
        for job in jobs[:10]:
            print(job)
        return 0

    log_dir = ROOT / "game_records" / "_batch_logs" / args.batch_name
    log_dir.mkdir(parents=True, exist_ok=True)
    launch_gate = LaunchGate(args.launch_stagger_seconds)
    failures = 0
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = [
            pool.submit(
                _run_one,
                job,
                batch_name=args.batch_name,
                model=args.decision_model,
                subagent_model=args.data_subagent_model,
                decision_agent_mode=args.decision_agent_mode,
                decision_interval=args.decision_interval,
                enemy_build=args.enemy_build,
                game_time_limit=args.game_time_limit,
                log_dir=log_dir,
                max_attempts=args.max_attempts,
                launch_gate=launch_gate,
                startup_timeout=args.startup_timeout,
            )
            for job in jobs
        ]
        for future in as_completed(futures):
            code, message = future.result()
            failures += int(code != 0)
            print(message, flush=True)
    print(f"finished: failures={failures}/{len(jobs)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
