import json
from pathlib import Path

import pytest

from tools.experiment_config import (
    ExperimentConfigError,
    load_experiment_suite,
    select_experiments,
    sweep_command,
    with_start_index,
)
from tools.run_experiment_config import main, tmux_session_name

ROOT = Path(__file__).resolve().parents[2]


def _config() -> dict:
    return {
        "schema_version": 1,
        "name": "unit_suite",
        "execution": {
            "backend": "foreground",
            "log_root": "game_records/_batch_logs/unit_suite",
        },
        "defaults": {
            "decision_model": "main-model",
            "data_subagent_model": "sub-model",
            "decision_interval": 60,
            "concurrency": 2,
            "repeats": 1,
            "game_time_limit": 300,
            "max_attempts": 2,
            "launch_stagger_seconds": 1,
            "startup_timeout": 90,
            "enemy_build": "macro",
            "strategies": ["four_gate"],
            "maps": ["KairosJunctionLE"],
            "bot_races": ["protoss"],
            "enemy_races": ["terran"],
            "difficulties": ["mediumhard"],
            "start_index": 0,
        },
        "experiments": [
            {
                "name": "v1",
                "batch_name": "unit_v1",
                "decision_agent_mode": "data-v2.2",
            },
            {
                "name": "v2",
                "batch_name": "unit_v2",
                "decision_agent_mode": "data-v2.2-v2",
                "decision_model": "override-model",
            },
        ],
    }


def _write_config(tmp_path: Path, value: dict) -> Path:
    path = tmp_path / "experiment.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_defaults_are_merged_with_per_experiment_overrides(tmp_path):
    suite = load_experiment_suite(_write_config(tmp_path, _config()))

    assert len(suite.experiments) == 2
    assert suite.experiments[0].values["decision_model"] == "main-model"
    assert suite.experiments[1].values["decision_model"] == "override-model"
    assert suite.experiments[1].values["data_subagent_model"] == "sub-model"
    assert all(experiment.job_count == 1 for experiment in suite.experiments)


def test_unknown_fields_are_rejected_instead_of_silently_ignored(tmp_path):
    value = _config()
    value["defaults"]["concurency"] = 12

    with pytest.raises(ExperimentConfigError, match="concurency"):
        load_experiment_suite(_write_config(tmp_path, value))


@pytest.mark.parametrize("duplicate_field", ["name", "batch_name"])
def test_duplicate_experiment_identity_is_rejected(tmp_path, duplicate_field):
    value = _config()
    source = value["experiments"][0][duplicate_field]
    value["experiments"][1][duplicate_field] = source

    with pytest.raises(ExperimentConfigError, match="duplicate"):
        load_experiment_suite(_write_config(tmp_path, value))


def test_disabled_experiments_are_not_selectable(tmp_path):
    value = _config()
    value["experiments"][1]["enabled"] = False
    suite = load_experiment_suite(_write_config(tmp_path, value))

    assert [experiment.name for experiment in suite.experiments] == ["v1"]
    with pytest.raises(ExperimentConfigError, match="unknown or disabled"):
        select_experiments(suite, ["v2"])


def test_sweep_command_converts_json_arrays_to_existing_cli_contract(tmp_path):
    suite = load_experiment_suite(_write_config(tmp_path, _config()))
    command = sweep_command(
        suite.experiments[0], start_index_override=7, python_executable="python"
    )

    assert command[:2] == [
        "python",
        str(ROOT / "tools" / "run_kimi_nothink_strategy_sweep.py"),
    ]
    assert command[command.index("--strategies") + 1] == "four_gate"
    assert command[command.index("--bot-races") + 1] == "protoss"
    assert command[command.index("--start-index") + 1] == "7"


def test_start_index_override_updates_resolved_manifest_values_and_job_count(tmp_path):
    value = _config()
    value["defaults"]["repeats"] = 3
    suite = load_experiment_suite(_write_config(tmp_path, value))

    resumed = with_start_index(suite.experiments[0], 2)

    assert resumed.values["start_index"] == 2
    assert resumed.job_count == 1


def test_repository_escape_in_log_root_is_rejected(tmp_path):
    value = _config()
    value["execution"]["log_root"] = "../outside"

    with pytest.raises(ExperimentConfigError, match="repository-relative"):
        load_experiment_suite(_write_config(tmp_path, value))


def test_log_root_must_stay_in_ignored_game_records(tmp_path):
    value = _config()
    value["execution"]["log_root"] = "docs/accidental-run-logs"

    with pytest.raises(ExperimentConfigError, match="inside the ignored game_records"):
        load_experiment_suite(_write_config(tmp_path, value))


def test_credentials_cannot_be_embedded_in_experiment_environment(tmp_path):
    value = _config()
    value["execution"]["environment"] = {"OPENAI_API_KEY": "do-not-store-here"}

    with pytest.raises(ExperimentConfigError, match="credential-bearing"):
        load_experiment_suite(_write_config(tmp_path, value))


def test_canonical_templates_each_resolve_to_450_jobs_per_group():
    template_root = ROOT / "experiment_configs" / "templates"
    three_mode = load_experiment_suite(
        template_root / "matrix450-three-mode.example.json"
    )
    four_group = load_experiment_suite(
        template_root / "matrix450-qwen-four-group.example.json"
    )

    assert [experiment.job_count for experiment in three_mode.experiments] == [450] * 3
    assert [experiment.job_count for experiment in four_group.experiments] == [450] * 4


def test_cli_dry_run_does_not_launch_sweeps(tmp_path, monkeypatch, capsys):
    path = _write_config(tmp_path, _config())

    def unexpected_run(*args, **kwargs):
        raise AssertionError("dry-run must not launch subprocesses")

    monkeypatch.setattr("tools.run_experiment_config.subprocess.run", unexpected_run)
    assert main(["--config", str(path), "--dry-run", "--experiment", "v2"]) == 0
    output = capsys.readouterr().out
    assert "experiments=1" in output
    assert "--decision-agent-mode data-v2.2-v2" in output


def test_tmux_session_name_is_stable_and_bounded():
    assert tmux_session_name("sc2exp", "matrix") == "sc2exp-matrix"
    assert len(tmux_session_name("p" * 50, "s" * 50)) == 80
