"""Run the paired 15-condition readable-skill ablation suite.

The same conditions are reused for the full method and every ablation so that
method is the only intended treatment variable. Existing completed matches are
discovered from their trace artifacts, making an interrupted suite resumable.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
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
    "full_v2": "human-skill-full-v2",
    "single_trace": "human-skill-single-trace",
    "static_population": "human-skill-static-population",
    "flat_adaptive": "human-skill-flat-adaptive",
    "positive_only": "human-skill-positive-only",
    "frequency_only": "human-skill-frequency-only",
}


@dataclass(frozen=True)
class Condition:
    index: int
    bot_race: str
    enemy_race: str
    skill_id: str
    enemy_build: str


class LaunchGate:
    """Serialize only the instant at which concurrent SC2 children start."""

    def __init__(self, stagger_seconds: float) -> None:
        self.stagger_seconds = max(0.0, float(stagger_seconds))
        self._lock = threading.Lock()
        self._last_launch = 0.0

    def wait(self) -> None:
        with self._lock:
            delay = self.stagger_seconds - (time.monotonic() - self._last_launch)
            if delay > 0:
                time.sleep(delay)
            self._last_launch = time.monotonic()


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


def _proc_ppid(proc_dir: Path) -> int | None:
    try:
        stat_text = (proc_dir / "stat").read_text(encoding="utf-8")
        _prefix, separator, suffix = stat_text.rpartition(")")
        if not separator:
            return None
        fields = suffix.strip().split()
        return int(fields[1])
    except (OSError, ValueError, IndexError):
        return None


def _process_tree(root_pid: int, proc_root: Path = Path("/proc")) -> set[int]:
    """Return root_pid and every discoverable descendant from procfs."""

    children: dict[int, list[int]] = {}
    try:
        entries = tuple(proc_root.iterdir())
    except OSError:
        return {root_pid}
    for entry in entries:
        if not entry.name.isdigit():
            continue
        ppid = _proc_ppid(entry)
        if ppid is not None:
            children.setdefault(ppid, []).append(int(entry.name))
    result = {root_pid}
    pending = [root_pid]
    while pending:
        parent = pending.pop()
        for child in children.get(parent, ()):
            if child not in result:
                result.add(child)
                pending.append(child)
    return result


def _process_forest(root_pids: Iterable[int], proc_root: Path = Path("/proc")) -> set[int]:
    """Return every process owned by all active jobs in this runner.

    A concurrent suite has sibling match roots.  Treating only one job's tree
    as owned makes each match misclassify the other runner jobs as foreign SC2.
    """

    result: set[int] = set()
    for root_pid in tuple(root_pids):
        result.update(_process_tree(root_pid, proc_root))
    return result


def _sc2_process_pids(proc_root: Path = Path("/proc")) -> set[int]:
    """Find native SC2 client processes without matching unrelated shells."""

    result: set[int] = set()
    try:
        entries = tuple(proc_root.iterdir())
    except OSError:
        return result
    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            command = (entry / "cmdline").read_bytes().replace(b"\0", b" ")
        except OSError:
            continue
        if b"/SC2_x64 " in command or command.rstrip().endswith(b"/SC2_x64"):
            result.add(int(entry.name))
    return result


def _process_has_trusted_owner_env(pid: int, trusted_owner_pid: int) -> bool:
    if trusted_owner_pid <= 0:
        return False
    try:
        environment = (Path("/proc") / str(pid) / "environ").read_bytes().split(b"\0")
    except OSError:
        return False
    expected = f"SC2_TRUSTED_OWNER_PID={trusted_owner_pid}".encode("ascii")
    return expected in environment


def _foreign_sc2_pids(
    owned_process_roots: Iterable[int],
    trusted_process_roots: Iterable[int],
    trusted_owner_pid: int = 0,
) -> list[int]:
    """Return SC2 clients outside the exact trusted process forest.

    Snapshot SC2 PIDs before resolving ownership. If a sibling client starts
    between the two scans, it is absent from the frozen candidate set instead
    of being falsely classified as foreign because it missed an older forest
    snapshot.
    """

    sc2_pids = _sc2_process_pids()
    owned_tree = _process_forest(
        set(owned_process_roots) | set(trusted_process_roots)
    )
    return sorted(
        pid
        for pid in sc2_pids - owned_tree
        if not _process_has_trusted_owner_env(pid, trusted_owner_pid)
    )


def _terminate_process_group(process: subprocess.Popen, timeout_seconds: float = 10.0) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=timeout_seconds)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    process.wait(timeout=timeout_seconds)


def _method_for_trace(trace: dict) -> str:
    decisions = trace.get("decisions") or []
    return str(decisions[0].get("skill_method") if decisions else "")


def record_has_watchdog(record_dir: Path) -> bool:
    try:
        match_log = (record_dir / "match.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        match_log = ""
    if (
        "SC2 protocol response timed out" in match_log
        or "Recovered stalled SC2 protocol request" in match_log
        or "SC2 client process exited" in match_log
        or "AI iteration timed out" in match_log
        or "SC2_PROCESS_DISAPPEARED" in match_log
    ):
        return True
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
    parser.add_argument(
        "--method",
        choices=tuple(METHODS),
        default=None,
        help="Run only one method; useful for synchronized per-ablation batches.",
    )
    parser.add_argument("--difficulty", default="mediumhard")
    parser.add_argument("--map-name", default="KairosJunctionLE")
    parser.add_argument("--game-time-limit", type=int, default=1200)
    parser.add_argument("--decision-interval", type=float, default=60.0)
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help=(
            "Independent SC2 child processes. Launches are staggered and each "
            "child is allowed to finish naturally."
        ),
    )
    parser.add_argument(
        "--retry-concurrency",
        type=int,
        default=1,
        help="Lower-concurrency retry pool used after invalid or failed matches.",
    )
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-backoff", type=float, default=15.0)
    parser.add_argument(
        "--wall-timeout",
        type=int,
        default=3000,
        help=(
            "Compatibility/audit value only. The stable high-concurrency path "
            "does not externally terminate a live SC2 protocol request."
        ),
    )
    parser.add_argument("--protocol-response-timeout", type=float, default=90.0)
    parser.add_argument(
        "--protocol-observation-timeout",
        type=float,
        default=120.0,
        help=(
            "Bound a slow SC2 observation response separately from ordinary "
            "protocol calls. The receive remains alive after this deadline so "
            "cleanup never starts a second websocket receive."
        ),
    )
    parser.add_argument(
        "--protocol-drain-timeout",
        type=float,
        default=10.0,
        help=(
            "Wait this long for an already-pending SC2 response during cleanup "
            "before killing only the owned client process."
        ),
    )
    parser.add_argument("--ai-step-timeout", type=float, default=180.0)
    parser.add_argument("--available-abilities-refresh-game-loops", type=int, default=44)
    parser.add_argument("--available-abilities-query-chunk-size", type=int, default=32)
    parser.add_argument(
        "--game-info-refresh-game-loops",
        type=int,
        default=0,
        help=(
            "Refresh the dynamic pathing grid at this SC2 game-loop interval; "
            "zero disables periodic refresh after the initial request."
        ),
    )
    parser.add_argument(
        "--launch-stagger",
        type=float,
        default=2.0,
        help="Minimum gap between child launches, matching the stable reference runner.",
    )
    parser.add_argument(
        "--foreign-sc2-wait-timeout",
        type=float,
        default=21600.0,
        help=(
            "Deprecated compatibility/audit value. The stable launcher does "
            "not poll or terminate unrelated SC2 process trees."
        ),
    )
    parser.add_argument("--batch-prefix", default="human_skill_ablation_1200_mediumhard_20260809")
    parser.add_argument("--manifest-name", default="suite_manifest.json")
    parser.add_argument("--model", default="DeepSeek-V4-flash")
    parser.add_argument("--indices", default="0-14")
    args = parser.parse_args()
    try:
        trusted_owner_pid = int(os.environ.get("SC2_TRUSTED_OWNER_PID", "0") or 0)
    except ValueError as exc:
        raise ValueError("SC2_TRUSTED_OWNER_PID must be an integer PID") from exc
    if trusted_owner_pid < 0:
        raise ValueError("SC2_TRUSTED_OWNER_PID cannot be negative")
    if args.concurrency < 1 or args.retry_concurrency < 1:
        raise ValueError("concurrency values must be positive")
    if args.max_attempts < 1 or args.retry_backoff < 0:
        raise ValueError("retry controls are invalid")
    if Path(args.manifest_name).name != args.manifest_name or not args.manifest_name.endswith(".json"):
        raise ValueError("manifest-name must be a plain .json file name")
    if (
        args.wall_timeout < 1
        or args.protocol_response_timeout <= 0
        or args.protocol_observation_timeout <= 0
        or args.protocol_drain_timeout < 0
        or args.ai_step_timeout <= 0
        or args.launch_stagger < 0
        or args.game_info_refresh_game_loops < 0
        or args.available_abilities_refresh_game_loops < 1
        or args.available_abilities_query_chunk_size < 1
        or args.foreign_sc2_wait_timeout <= 0
    ):
        raise ValueError("timeouts must be positive")

    methods = list(selected_methods(args.phase))
    if args.method is not None:
        methods = [(args.method, METHODS[args.method])]
    indices = selected_indices(args.indices)
    conditions = tuple(item for item in CONDITIONS if item.index in indices)
    state_root = ROOT / "game_records" / "_human_skill_ablation"
    log_root = state_root / args.batch_prefix
    log_root.mkdir(parents=True, exist_ok=True)
    manifest_path = log_root / args.manifest_name
    manifest_lock = threading.Lock()
    manifest = {
        "schema_version": 4,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "phase": args.phase,
        "difficulty": args.difficulty,
        "map_name": args.map_name,
        "game_time_limit": args.game_time_limit,
        "decision_interval": args.decision_interval,
        "concurrency": args.concurrency,
        "wall_timeout": args.wall_timeout,
        "protocol_response_timeout": args.protocol_response_timeout,
        "protocol_observation_timeout": args.protocol_observation_timeout,
        "protocol_drain_timeout": args.protocol_drain_timeout,
        "ai_step_timeout": args.ai_step_timeout,
        "game_info_refresh_game_loops": args.game_info_refresh_game_loops,
        "available_abilities_refresh_game_loops": args.available_abilities_refresh_game_loops,
        "available_abilities_query_chunk_size": args.available_abilities_query_chunk_size,
        "launch_stagger": args.launch_stagger,
        "foreign_sc2_wait_timeout": args.foreign_sc2_wait_timeout,
        "trusted_owner_pid": trusted_owner_pid or None,
        "launcher_mode": "natural_subprocess_run",
        "launcher_reference": (
            "/data2/shy_2608/SC2-Agent-knowlegde/"
            "tools/run_structural_baseline_smoke10.py"
        ),
        "wall_timeout_enforced": False,
        "foreign_sc2_runtime_monitor": False,
        "retry_concurrency": args.retry_concurrency,
        "max_attempts": args.max_attempts,
        "retry_backoff": args.retry_backoff,
        "runtime_failure_policy": "natural_child_exit_validate_then_retry_serially",
        "global_wineserver_kill_allowed": False,
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
    launch_gate = LaunchGate(args.launch_stagger)

    def run_job(job: tuple[str, str, Condition, str, Path], attempt: int) -> dict:
        method_name, agent, condition, batch_name, log_path = job
        launch_gate.wait()
        command = [
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
                "SC2_PROTOCOL_OBSERVATION_TIMEOUT_SECONDS": str(
                    args.protocol_observation_timeout
                ),
                "SC2_PROTOCOL_DRAIN_TIMEOUT_SECONDS": str(args.protocol_drain_timeout),
                "SC2_AI_STEP_TIMEOUT_SECONDS": str(args.ai_step_timeout),
                # The OpenAI client is synchronous inside the bot step, so an
                # asyncio wait_for cannot interrupt a blocked HTTP read.  Keep
                # each SDK attempt bounded; the SDK's own retries still fit
                # within the 180-second AI-step budget in ordinary operation.
                "SC2_LLM_REQUEST_TIMEOUT_SECONDS": "60",
                "SC2_GAME_INFO_REFRESH_GAME_LOOPS": str(args.game_info_refresh_game_loops),
                "SC2_AVAILABLE_ABILITIES_REFRESH_GAME_LOOPS": str(
                    args.available_abilities_refresh_game_loops
                ),
                "SC2_AVAILABLE_ABILITIES_QUERY_CHUNK_SIZE": str(
                    args.available_abilities_query_chunk_size
                ),
                "SC2_VERBOSE_LOG": "0",
                "SC2_ALLOW_GLOBAL_WINESERVER_KILL": "0",
                "PYTHONUNBUFFERED": "1",
            }
        )
        started = time.time()
        attempt_log_path = log_path.with_suffix(f".attempt{attempt}.log")
        with attempt_log_path.open("w", encoding="utf-8") as log:
            log.write("LAUNCHER_MODE natural_subprocess_run\n")
            log.write("SC2_LLM_REQUEST_TIMEOUT_SECONDS 60\n")
            log.write("External process-group watchdog disabled; waiting for child exit.\n")
            log.flush()
            completed_process = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
            process_returncode = completed_process.returncode
        artifact_complete = condition.skill_id in completed_skill_ids(ROOT / "game_records" / batch_name)
        complete = process_returncode == 0 and artifact_complete
        return {
            "method": method_name,
            "agent": agent,
            "condition": asdict(condition),
            "batch_name": batch_name,
            "attempt": attempt,
            "log_path": str(attempt_log_path.relative_to(ROOT)),
            "status": "complete" if complete else "retryable_failure",
            "returncode": process_returncode,
            "artifact_complete": artifact_complete,
            "foreign_sc2_overlap_pids": [],
            "failure_reason": (
                ""
                if complete
                else "nonzero_exit"
                if process_returncode
                else "invalid_or_watchdog_artifact"
            ),
            "wall_seconds": round(time.time() - started, 2),
        }

    pending = list(jobs)
    attempt_failure_count = 0
    for attempt in range(1, args.max_attempts + 1):
        if not pending:
            break
        if attempt > 1 and args.retry_backoff:
            print(
                f"retry wave {attempt}/{args.max_attempts} pending={len(pending)} "
                f"backoff={args.retry_backoff}s",
                flush=True,
            )
            time.sleep(args.retry_backoff)
        workers = args.concurrency if attempt == 1 else args.retry_concurrency
        workers = min(workers, len(pending))
        next_pending: list[tuple[str, str, Condition, str, Path]] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(run_job, job, attempt): job for job in pending}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    method_name, agent, condition, batch_name, log_path = job
                    result = {
                        "method": method_name,
                        "agent": agent,
                        "condition": asdict(condition),
                        "batch_name": batch_name,
                        "attempt": attempt,
                        "log_path": str(log_path.relative_to(ROOT)),
                        "status": "retryable_failure",
                        "returncode": None,
                        "artifact_complete": False,
                        "failure_reason": f"runner_exception:{exc!r}",
                        "wall_seconds": 0.0,
                    }
                if result["status"] != "complete":
                    attempt_failure_count += 1
                    next_pending.append(job)
                with manifest_lock:
                    manifest["jobs"].append(result)
                    save_manifest()
                print(
                    f"[attempt {attempt}] {result['method']} "
                    f"{result['condition']['skill_id']} {result['status']} "
                    f"wall={result['wall_seconds']}s",
                    flush=True,
                )
        pending = next_pending

    failures = len(pending)
    if failures:
        failed_keys = {
            f"{method_name}:{condition.skill_id}"
            for method_name, _agent, condition, _batch_name, _log_path in pending
        }
        manifest["terminal_failures"] = sorted(failed_keys)
    manifest["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    manifest["failure_count"] = failures
    manifest["attempt_failure_count"] = attempt_failure_count
    save_manifest()
    print(f"suite complete failures={failures} manifest={manifest_path}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
