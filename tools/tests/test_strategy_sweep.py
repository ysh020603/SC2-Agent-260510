import os

import pytest

from tools.run_kimi_nothink_strategy_sweep import LaunchGate, _child_environment, _jobs


def test_strategy_sweep_carries_bot_race_into_every_job():
    jobs = _jobs(
        ["four_gate"],
        ["KairosJunctionLE"],
        ["protoss"],
        ["terran", "zerg"],
        ["easy"],
        1,
    )
    assert [job.bot_race for job in jobs] == ["protoss", "protoss"]
    assert [job.enemy_race for job in jobs] == ["terran", "zerg"]
    assert all(job.match_prefix.startswith("p_") for job in jobs)


def test_strategy_sweep_rejects_cross_race_strategy_mistakes():
    with pytest.raises(ValueError, match="protoss/bio"):
        _jobs(
            ["bio"],
            ["KairosJunctionLE"],
            ["protoss"],
            ["terran"],
            ["easy"],
            1,
        )


def test_strategy_sweep_rejects_existing_but_disabled_strategy():
    with pytest.raises(ValueError, match="terran/battle_cruisers"):
        _jobs(
            ["battle_cruisers"],
            ["KairosJunctionLE"],
            ["terran"],
            ["protoss"],
            ["easy"],
            1,
        )


def test_enabled_sweep_expands_to_five_strategies_per_race():
    jobs = _jobs(
        ["enabled"],
        ["KairosJunctionLE"],
        ["terran", "protoss", "zerg"],
        ["terran"],
        ["easy"],
        1,
    )
    assert len(jobs) == 15
    assert {job.bot_race for job in jobs} == {"terran", "protoss", "zerg"}


def test_strategy_sweep_does_not_inject_linux_sc2_path_on_windows(
    monkeypatch,
):
    monkeypatch.delenv("SC2PATH", raising=False)
    monkeypatch.setattr(os, "name", "nt")
    assert "SC2PATH" not in _child_environment()


def test_strategy_sweep_child_logs_are_unbuffered_and_startup_is_bounded():
    env = _child_environment(startup_timeout=75)
    assert env["PYTHONUNBUFFERED"] == "1"
    assert env["SC2_STARTUP_TIMEOUT"] == "75.0"


def test_launch_gate_clamps_negative_stagger_to_zero():
    assert LaunchGate(-1).stagger_seconds == 0.0
