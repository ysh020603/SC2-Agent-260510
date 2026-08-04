"""Load and validate reproducible strategy-sweep experiment configurations."""

from __future__ import annotations

import hashlib
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.run_kimi_nothink_strategy_sweep import _jobs

SCHEMA_VERSION = 1
DECISION_AGENT_MODES = {
    "naive",
    "data-v2.2",
    "data-v2.2-v2",
    "data-v2.2-v2-no-knowledge",
}
RACES = {"terran", "protoss", "zerg"}
DIFFICULTIES = {
    "veryeasy",
    "easy",
    "medium",
    "mediumhard",
    "hard",
    "harder",
    "veryhard",
    "vision",
    "money",
    "insane",
}
ENEMY_BUILDS = {"random", "rush", "timing", "power", "macro", "air"}

SWEEP_FIELDS = {
    "batch_name",
    "decision_model",
    "data_subagent_model",
    "decision_agent_mode",
    "decision_interval",
    "concurrency",
    "repeats",
    "game_time_limit",
    "max_attempts",
    "launch_stagger_seconds",
    "startup_timeout",
    "enemy_build",
    "strategies",
    "maps",
    "bot_races",
    "enemy_races",
    "difficulties",
    "start_index",
}
LIST_FIELDS = {"strategies", "maps", "bot_races", "enemy_races", "difficulties"}
INTEGER_FIELDS = {
    "concurrency",
    "repeats",
    "game_time_limit",
    "max_attempts",
    "start_index",
}
NUMBER_FIELDS = {"decision_interval", "launch_stagger_seconds", "startup_timeout"}
TOP_LEVEL_FIELDS = {
    "$schema",
    "schema_version",
    "name",
    "description",
    "execution",
    "defaults",
    "experiments",
}
EXECUTION_FIELDS = {
    "backend",
    "parallel_experiments",
    "max_parallel_experiments",
    "experiment_stagger_seconds",
    "log_root",
    "tmux_session_prefix",
    "replace_existing_tmux_session",
    "environment",
}
EXPERIMENT_FIELDS = SWEEP_FIELDS | {"name", "description", "enabled"}
SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
SAFE_ENVIRONMENT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SECRET_ENVIRONMENT_NAME = re.compile(
    r"(?:API_?KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.IGNORECASE
)


class ExperimentConfigError(ValueError):
    """Raised when an experiment config cannot be safely reproduced."""


@dataclass(frozen=True)
class ExecutionConfig:
    backend: str
    parallel_experiments: bool
    max_parallel_experiments: int
    experiment_stagger_seconds: float
    log_root: Path
    tmux_session_prefix: str
    replace_existing_tmux_session: bool
    environment: dict[str, str]


@dataclass(frozen=True)
class ResolvedExperiment:
    name: str
    description: str
    values: dict[str, Any]
    job_count: int

    @property
    def batch_name(self) -> str:
        return str(self.values["batch_name"])


@dataclass(frozen=True)
class ExperimentSuite:
    path: Path
    name: str
    description: str
    execution: ExecutionConfig
    experiments: tuple[ResolvedExperiment, ...]
    source_hash: str


def _expect_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExperimentConfigError(f"{label} must be a JSON object")
    return dict(value)


def _reject_unknown(value: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ExperimentConfigError(f"{label} has unknown field(s): {', '.join(unknown)}")


def _required_string(value: Any, label: str, *, component: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExperimentConfigError(f"{label} must be a non-empty string")
    result = value.strip()
    if component and not SAFE_COMPONENT.fullmatch(result):
        raise ExperimentConfigError(
            f"{label} must contain only letters, digits, '.', '_' or '-' and "
            "must start with a letter or digit"
        )
    return result


def _optional_string(value: Any, label: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ExperimentConfigError(f"{label} must be a string")
    return value.strip()


def _positive_integer(value: Any, label: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExperimentConfigError(f"{label} must be an integer")
    minimum = 0 if allow_zero else 1
    if value < minimum:
        raise ExperimentConfigError(f"{label} must be >= {minimum}")
    return value


def _nonnegative_number(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ExperimentConfigError(f"{label} must be a number")
    result = float(value)
    minimum = "greater than zero" if positive else ">= 0"
    if (positive and result <= 0) or (not positive and result < 0):
        raise ExperimentConfigError(f"{label} must be {minimum}")
    return result


def _safe_repo_relative_path(value: Any, label: str) -> Path:
    text = _required_string(value, label)
    candidate = Path(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ExperimentConfigError(f"{label} must be a repository-relative path without '..'")
    resolved = (ROOT / candidate).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise ExperimentConfigError(f"{label} escapes the repository") from exc
    return resolved


def _validate_execution(raw: Any) -> ExecutionConfig:
    value = _expect_mapping({} if raw is None else raw, "execution")
    _reject_unknown(value, EXECUTION_FIELDS, "execution")
    backend = value.get("backend", "foreground")
    if backend not in {"foreground", "tmux"}:
        raise ExperimentConfigError("execution.backend must be 'foreground' or 'tmux'")
    parallel = value.get("parallel_experiments", False)
    replace = value.get("replace_existing_tmux_session", False)
    if not isinstance(parallel, bool):
        raise ExperimentConfigError("execution.parallel_experiments must be boolean")
    if not isinstance(replace, bool):
        raise ExperimentConfigError(
            "execution.replace_existing_tmux_session must be boolean"
        )
    max_parallel = _positive_integer(
        value.get("max_parallel_experiments", 1),
        "execution.max_parallel_experiments",
    )
    stagger = _nonnegative_number(
        value.get("experiment_stagger_seconds", 0),
        "execution.experiment_stagger_seconds",
    )
    log_root = _safe_repo_relative_path(
        value.get("log_root", "game_records/_batch_logs/config_runs"),
        "execution.log_root",
    )
    try:
        log_root.relative_to((ROOT / "game_records").resolve())
    except ValueError as exc:
        raise ExperimentConfigError(
            "execution.log_root must be inside the ignored game_records directory"
        ) from exc
    prefix = _required_string(
        value.get("tmux_session_prefix", "sc2exp"),
        "execution.tmux_session_prefix",
        component=True,
    )
    environment = _expect_mapping(value.get("environment", {}), "execution.environment")
    normalized_environment: dict[str, str] = {}
    for key, item in environment.items():
        if not isinstance(key, str) or not SAFE_ENVIRONMENT_NAME.fullmatch(key):
            raise ExperimentConfigError(f"invalid environment variable name: {key!r}")
        if SECRET_ENVIRONMENT_NAME.search(key):
            raise ExperimentConfigError(
                f"execution.environment.{key} looks credential-bearing; "
                "put credentials in ignored API_config/config.json"
            )
        if not isinstance(item, str):
            raise ExperimentConfigError(f"execution.environment.{key} must be a string")
        normalized_environment[key] = item
    return ExecutionConfig(
        backend=backend,
        parallel_experiments=parallel,
        max_parallel_experiments=max_parallel,
        experiment_stagger_seconds=stagger,
        log_root=log_root,
        tmux_session_prefix=prefix,
        replace_existing_tmux_session=replace,
        environment=normalized_environment,
    )


def _validate_sweep_values(values: dict[str, Any], label: str) -> tuple[dict[str, Any], int]:
    missing = sorted(SWEEP_FIELDS - set(values))
    if missing:
        raise ExperimentConfigError(f"{label} is missing resolved field(s): {', '.join(missing)}")

    normalized: dict[str, Any] = {}
    for field in SWEEP_FIELDS:
        item = values[field]
        field_label = f"{label}.{field}"
        if field in LIST_FIELDS:
            if not isinstance(item, list) or not item:
                raise ExperimentConfigError(f"{field_label} must be a non-empty JSON array")
            normalized[field] = [
                _required_string(entry, f"{field_label}[{index}]")
                for index, entry in enumerate(item)
            ]
            if any("," in entry for entry in normalized[field]):
                raise ExperimentConfigError(
                    f"{field_label} entries cannot contain ',' because the sweep CLI "
                    "uses comma-separated lists"
                )
        elif field in INTEGER_FIELDS:
            normalized[field] = _positive_integer(
                item, field_label, allow_zero=(field == "start_index")
            )
        elif field in NUMBER_FIELDS:
            normalized[field] = _nonnegative_number(
                item, field_label, positive=(field in {"decision_interval", "startup_timeout"})
            )
        else:
            normalized[field] = _required_string(
                item, field_label, component=(field == "batch_name")
            )

    if normalized["decision_agent_mode"] not in DECISION_AGENT_MODES:
        raise ExperimentConfigError(
            f"{label}.decision_agent_mode is not supported: "
            f"{normalized['decision_agent_mode']}"
        )
    if normalized["enemy_build"] not in ENEMY_BUILDS:
        raise ExperimentConfigError(f"{label}.enemy_build is not supported")
    for field in ("bot_races", "enemy_races"):
        invalid = sorted(set(normalized[field]) - RACES)
        if invalid:
            raise ExperimentConfigError(f"{label}.{field} has invalid race(s): {', '.join(invalid)}")
    invalid_difficulties = sorted(set(normalized["difficulties"]) - DIFFICULTIES)
    if invalid_difficulties:
        raise ExperimentConfigError(
            f"{label}.difficulties has invalid value(s): {', '.join(invalid_difficulties)}"
        )

    try:
        all_jobs = _jobs(
            normalized["strategies"],
            normalized["maps"],
            normalized["bot_races"],
            normalized["enemy_races"],
            normalized["difficulties"],
            normalized["repeats"],
        )
    except ValueError as exc:
        raise ExperimentConfigError(f"{label}: {exc}") from exc
    remaining = sum(job.index >= normalized["start_index"] for job in all_jobs)
    return normalized, remaining


def load_experiment_suite(path: Path | str) -> ExperimentSuite:
    config_path = Path(path).expanduser().resolve()
    try:
        source = config_path.read_bytes()
    except OSError as exc:
        raise ExperimentConfigError(f"cannot read config {config_path}: {exc}") from exc
    try:
        raw = json.loads(source.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExperimentConfigError(f"invalid JSON in {config_path}: {exc}") from exc
    value = _expect_mapping(raw, "config")
    _reject_unknown(value, TOP_LEVEL_FIELDS, "config")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ExperimentConfigError(
            f"schema_version must be {SCHEMA_VERSION}, got {value.get('schema_version')!r}"
        )
    name = _required_string(value.get("name"), "name", component=True)
    description = _optional_string(value.get("description"), "description")
    execution = _validate_execution(value.get("execution", {}))
    defaults = _expect_mapping(value.get("defaults", {}), "defaults")
    _reject_unknown(defaults, SWEEP_FIELDS, "defaults")
    raw_experiments = value.get("experiments")
    if not isinstance(raw_experiments, list) or not raw_experiments:
        raise ExperimentConfigError("experiments must be a non-empty JSON array")

    resolved: list[ResolvedExperiment] = []
    names: set[str] = set()
    batch_names: set[str] = set()
    for index, raw_experiment in enumerate(raw_experiments):
        experiment = _expect_mapping(raw_experiment, f"experiments[{index}]")
        _reject_unknown(experiment, EXPERIMENT_FIELDS, f"experiments[{index}]")
        enabled = experiment.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ExperimentConfigError(f"experiments[{index}].enabled must be boolean")
        experiment_name = _required_string(
            experiment.get("name"), f"experiments[{index}].name", component=True
        )
        if experiment_name in names:
            raise ExperimentConfigError(f"duplicate experiment name: {experiment_name}")
        names.add(experiment_name)
        if not enabled:
            continue
        merged = dict(defaults)
        merged.update({key: item for key, item in experiment.items() if key in SWEEP_FIELDS})
        normalized, job_count = _validate_sweep_values(
            merged, f"experiments[{index}] ({experiment_name})"
        )
        batch_name = normalized["batch_name"]
        if batch_name in batch_names:
            raise ExperimentConfigError(f"duplicate enabled batch_name: {batch_name}")
        batch_names.add(batch_name)
        resolved.append(
            ResolvedExperiment(
                name=experiment_name,
                description=_optional_string(
                    experiment.get("description"),
                    f"experiments[{index}].description",
                ),
                values=normalized,
                job_count=job_count,
            )
        )
    if not resolved:
        raise ExperimentConfigError("at least one experiment must be enabled")
    return ExperimentSuite(
        path=config_path,
        name=name,
        description=description,
        execution=execution,
        experiments=tuple(resolved),
        source_hash=hashlib.sha256(source).hexdigest(),
    )


def select_experiments(
    suite: ExperimentSuite, selected_names: Optional[Sequence[str]] = None
) -> tuple[ResolvedExperiment, ...]:
    if not selected_names:
        return suite.experiments
    requested = list(dict.fromkeys(selected_names))
    known = {experiment.name: experiment for experiment in suite.experiments}
    missing = [name for name in requested if name not in known]
    if missing:
        raise ExperimentConfigError(
            "unknown or disabled experiment(s): " + ", ".join(missing)
        )
    return tuple(known[name] for name in requested)


def with_start_index(
    experiment: ResolvedExperiment, start_index: int
) -> ResolvedExperiment:
    """Return an experiment whose resolved values and count include a resume override."""

    normalized_start = _positive_integer(
        start_index, "start-index override", allow_zero=True
    )
    values = dict(experiment.values)
    values["start_index"] = normalized_start
    all_jobs = _jobs(
        values["strategies"],
        values["maps"],
        values["bot_races"],
        values["enemy_races"],
        values["difficulties"],
        values["repeats"],
    )
    return replace(
        experiment,
        values=values,
        job_count=sum(job.index >= normalized_start for job in all_jobs),
    )


def sweep_command(
    experiment: ResolvedExperiment,
    *,
    start_index_override: Optional[int] = None,
    python_executable: Optional[str] = None,
) -> list[str]:
    values = dict(experiment.values)
    if start_index_override is not None:
        values["start_index"] = _positive_integer(
            start_index_override, "start-index override", allow_zero=True
        )
    command = [
        python_executable or sys.executable,
        str(ROOT / "tools" / "run_kimi_nothink_strategy_sweep.py"),
    ]
    for field in (
        "batch_name",
        "decision_model",
        "data_subagent_model",
        "decision_agent_mode",
        "decision_interval",
        "concurrency",
        "repeats",
        "game_time_limit",
        "max_attempts",
        "launch_stagger_seconds",
        "startup_timeout",
        "enemy_build",
        "strategies",
        "maps",
        "bot_races",
        "enemy_races",
        "difficulties",
        "start_index",
    ):
        value = values[field]
        if field in LIST_FIELDS:
            value = ",".join(value)
        command.extend(["--" + field.replace("_", "-"), str(value)])
    return command


def display_command(command: Sequence[str]) -> str:
    return shlex.join(str(item) for item in command)


def git_commit() -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None
