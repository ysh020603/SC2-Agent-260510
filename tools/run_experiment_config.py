"""Validate, inspect, and execute versioned strategy-sweep configurations."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.experiment_config import (
    ExperimentConfigError,
    ExperimentSuite,
    ResolvedExperiment,
    display_command,
    git_commit,
    load_experiment_suite,
    select_experiments,
    sweep_command,
    with_start_index,
)


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one or more existing SC2 strategy sweeps from JSON.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--config", required=True, type=Path)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--validate", action="store_true", help="Validate and exit.")
    action.add_argument(
        "--dry-run", action="store_true", help="Print resolved commands without launching."
    )
    action.add_argument(
        "--print-commands", action="store_true", help="Print shell-ready commands and exit."
    )
    parser.add_argument(
        "--experiment",
        action="append",
        dest="experiments",
        help="Run only this enabled experiment name; repeat to select several.",
    )
    parser.add_argument(
        "--start-index",
        type=int,
        help="Temporarily override start_index for every selected experiment.",
    )
    parser.add_argument(
        "--backend",
        choices=("foreground", "tmux"),
        help="Temporarily override execution.backend.",
    )
    return parser.parse_args(argv)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _manifest_payload(
    suite: ExperimentSuite,
    experiments: Sequence[ResolvedExperiment],
    commands: dict[str, list[str]],
    backend: str,
) -> dict[str, Any]:
    created = datetime.now(timezone.utc).isoformat()
    return {
        "manifest_version": 1,
        "suite_name": suite.name,
        "config_path": str(suite.path),
        "config_sha256": suite.source_hash,
        "git_commit": git_commit(),
        "host": platform.node(),
        "platform": platform.platform(),
        "python": sys.version,
        "backend": backend,
        "execution": {
            "parallel_experiments": suite.execution.parallel_experiments,
            "max_parallel_experiments": suite.execution.max_parallel_experiments,
            "experiment_stagger_seconds": suite.execution.experiment_stagger_seconds,
            "log_root": str(suite.execution.log_root),
            "environment": suite.execution.environment,
        },
        "created_at": created,
        "updated_at": created,
        "experiments": {
            experiment.name: {
                "description": experiment.description,
                "batch_name": experiment.batch_name,
                "job_count": experiment.job_count,
                "resolved": experiment.values,
                "command": commands[experiment.name],
                "status": "pending",
                "exit_code": None,
            }
            for experiment in experiments
        },
    }


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def _runtime_environment(suite: ExperimentSuite) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(suite.execution.environment)
    environment.setdefault("PYTHONUTF8", "1")
    environment.setdefault("PYTHONIOENCODING", "utf-8")
    environment.setdefault("PYTHONUNBUFFERED", "1")
    return environment


def _run_experiment(
    experiment: ResolvedExperiment,
    command: list[str],
    *,
    suite: ExperimentSuite,
    manifest_path: Path,
    manifest: dict[str, Any],
    manifest_lock: threading.Lock,
) -> tuple[str, int]:
    log_path = suite.execution.log_root / f"{experiment.batch_name}.orchestrator.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    with manifest_lock:
        record = manifest["experiments"][experiment.name]
        record["status"] = "running"
        record["started_at"] = started
        manifest["updated_at"] = started
        _write_manifest(manifest_path, manifest)
    print(
        f"START name={experiment.name} batch={experiment.batch_name} "
        f"jobs={experiment.job_count} log={log_path}",
        flush=True,
    )
    exit_code = 1
    failure_detail = None
    try:
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n===== START {started} =====\n")
            log.write("CMD: " + display_command(command) + "\n")
            log.flush()
            try:
                result = subprocess.run(
                    command,
                    cwd=ROOT,
                    env=_runtime_environment(suite),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                )
                exit_code = result.returncode
            except OSError as exc:
                failure_detail = f"cannot launch sweep: {exc}"
                log.write(f"ERROR: {failure_detail}\n")
            ended = datetime.now(timezone.utc).isoformat()
            log.write(f"===== END exit={exit_code} {ended} =====\n")
    except OSError as exc:
        ended = datetime.now(timezone.utc).isoformat()
        failure_detail = f"cannot write orchestration log {log_path}: {exc}"
    with manifest_lock:
        record = manifest["experiments"][experiment.name]
        record["status"] = "completed" if exit_code == 0 else "failed"
        record["exit_code"] = exit_code
        if failure_detail:
            record["error"] = failure_detail
        record["ended_at"] = ended
        manifest["updated_at"] = ended
        _write_manifest(manifest_path, manifest)
    print(f"END name={experiment.name} exit={exit_code}", flush=True)
    return experiment.name, exit_code


def _execute_foreground(
    suite: ExperimentSuite,
    experiments: Sequence[ResolvedExperiment],
    commands: dict[str, list[str]],
) -> int:
    manifest_path = (
        ROOT
        / "game_records"
        / "_experiment_manifests"
        / f"{suite.name}_{_timestamp()}.json"
    )
    manifest = _manifest_payload(suite, experiments, commands, "foreground")
    _write_manifest(manifest_path, manifest)
    print(f"manifest={manifest_path}", flush=True)
    manifest_lock = threading.Lock()
    max_workers = (
        min(suite.execution.max_parallel_experiments, len(experiments))
        if suite.execution.parallel_experiments
        else 1
    )
    failures = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = []
        for index, experiment in enumerate(experiments):
            if index and suite.execution.experiment_stagger_seconds:
                time.sleep(suite.execution.experiment_stagger_seconds)
            futures.append(
                pool.submit(
                    _run_experiment,
                    experiment,
                    commands[experiment.name],
                    suite=suite,
                    manifest_path=manifest_path,
                    manifest=manifest,
                    manifest_lock=manifest_lock,
                )
            )
        for future in as_completed(futures):
            _, exit_code = future.result()
            failures += int(exit_code != 0)
    print(f"suite finished: failures={failures}/{len(experiments)}")
    return 1 if failures else 0


def tmux_session_name(prefix: str, suite_name: str) -> str:
    value = f"{prefix}-{suite_name}"
    return value[:80]


def _launch_tmux(
    suite: ExperimentSuite,
    selected_names: Sequence[str],
    start_index: Optional[int],
) -> int:
    if os.name == "nt":
        raise ExperimentConfigError("tmux backend is supported only on Linux/macOS hosts")
    session_name = tmux_session_name(suite.execution.tmux_session_prefix, suite.name)
    try:
        existing = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode == 0
    except OSError as exc:
        raise ExperimentConfigError(f"cannot invoke tmux: {exc}") from exc
    if existing and not suite.execution.replace_existing_tmux_session:
        raise ExperimentConfigError(
            f"tmux session {session_name!r} already exists; choose another prefix or set "
            "replace_existing_tmux_session=true"
        )
    if existing:
        try:
            subprocess.run(["tmux", "kill-session", "-t", session_name], check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ExperimentConfigError(
                f"cannot replace tmux session {session_name!r}: {exc}"
            ) from exc

    inner = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--config",
        str(suite.path),
        "--backend",
        "foreground",
    ]
    for name in selected_names:
        inner.extend(["--experiment", name])
    if start_index is not None:
        inner.extend(["--start-index", str(start_index)])
    log_path = suite.execution.log_root / f"{suite.name}.tmux.log"
    tmux_environment = {
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        **suite.execution.environment,
    }
    environment = " ".join(
        f"{key}={shlex.quote(value)}" for key, value in tmux_environment.items()
    )
    shell_command = (
        f"cd {shlex.quote(str(ROOT))} && exec env {environment} "
        f"{display_command(inner)} >> {shlex.quote(str(log_path))} 2>&1"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                session_name,
                "bash",
                "-lc",
                shell_command,
            ],
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ExperimentConfigError(
            f"cannot create tmux session {session_name!r}: {exc}"
        ) from exc
    print(f"launched tmux session={session_name} log={log_path}")
    print(f"attach: tmux attach -t {shlex.quote(session_name)}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    try:
        suite = load_experiment_suite(args.config)
        experiments = select_experiments(suite, args.experiments)
        if args.start_index is not None:
            experiments = tuple(
                with_start_index(experiment, args.start_index)
                for experiment in experiments
            )
        commands = {
            experiment.name: sweep_command(experiment)
            for experiment in experiments
        }
        total_jobs = sum(experiment.job_count for experiment in experiments)
        print(
            f"valid suite={suite.name} experiments={len(experiments)} "
            f"configured_jobs={total_jobs} sha256={suite.source_hash[:12]}"
        )
        for experiment in experiments:
            print(
                f"  {experiment.name}: mode={experiment.values['decision_agent_mode']} "
                f"model={experiment.values['decision_model']} "
                f"jobs={experiment.job_count} batch={experiment.batch_name}"
            )
        if args.validate:
            return 0
        if args.dry_run or args.print_commands:
            for experiment in experiments:
                print(f"[{experiment.name}] {display_command(commands[experiment.name])}")
            return 0
        backend = args.backend or suite.execution.backend
        if backend == "tmux":
            return _launch_tmux(
                suite,
                [experiment.name for experiment in experiments],
                args.start_index,
            )
        return _execute_foreground(suite, experiments, commands)
    except ExperimentConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
