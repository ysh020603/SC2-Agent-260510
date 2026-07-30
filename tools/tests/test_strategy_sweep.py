import os

import pytest

from tools.run_kimi_nothink_strategy_sweep import _child_environment, _jobs


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


def test_strategy_sweep_does_not_inject_linux_sc2_path_on_windows(
    monkeypatch,
):
    monkeypatch.delenv("SC2PATH", raising=False)
    monkeypatch.setattr(os, "name", "nt")
    assert "SC2PATH" not in _child_environment()
