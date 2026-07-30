import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from SC2_Agent.execution.command import DONE, RUNNING, PlannedAction
from SC2_Agent.execution.direct_build import DirectBuildExecutor


def _supply_depot_action() -> PlannedAction:
    action = PlannedAction(
        action_name="TERRANBUILD_SUPPLYDEPOT",
        category="build",
        canonical_name="SupplyDepot",
        target_result="SupplyDepot",
        quantity=1,
    )
    action._direct_build_target_count = 1
    return action


def _executor_with_progress(monkeypatch, progress):
    executor = DirectBuildExecutor(SimpleNamespace())
    monkeypatch.setattr(executor, "_ensure_helper", AsyncMock())
    monkeypatch.setattr(executor, "_purge_reservations", lambda *_args: None)
    monkeypatch.setattr(executor, "_owned_progress_counts", lambda *_args: progress)
    monkeypatch.setattr(executor, "_refresh_issued_count", lambda *_args, **_kwargs: None)
    return executor


def test_direct_build_worker_order_does_not_mark_action_done(monkeypatch):
    executor = _executor_with_progress(monkeypatch, (0, 1, 0))
    action = _supply_depot_action()

    handled = asyncio.run(executor.mark_done_if_satisfied(action, now=10.0))

    assert handled
    assert action.state == RUNNING
    assert "awaiting foundation" in action.note


def test_direct_build_real_foundation_marks_action_done(monkeypatch):
    executor = _executor_with_progress(monkeypatch, (1, 0, 0))
    monkeypatch.setattr(executor, "clear_worker", lambda *_args: None)
    monkeypatch.setattr(executor, "_emit", lambda *_args: None)
    action = _supply_depot_action()

    handled = asyncio.run(executor.mark_done_if_satisfied(action, now=10.0))

    assert handled
    assert action.state == DONE
    assert "foundation confirmed" in action.note


def test_direct_build_en_route_progress_is_retained_at_timeout(monkeypatch):
    executor = _executor_with_progress(monkeypatch, (0, 1, 0))
    action = _supply_depot_action()

    retained = executor.keep_waiting_if_progressing(action, now=40.0)

    assert retained
    assert "direct build progress" in action.note


def test_scheduler_does_not_use_older_same_type_buildings_as_direct_completion(
    monkeypatch,
):
    from SC2_Agent.execution.scheduler import ExecutionScheduler

    scheduler = ExecutionScheduler()
    scheduler._equivalent_existing_count = lambda _unit_type: 6
    executor = DirectBuildExecutor(scheduler)
    scheduler._direct_build_executor = executor
    monkeypatch.setattr(executor, "_owned_progress_counts", lambda *_args: (0, 1, 0))
    action = _supply_depot_action()

    assert not scheduler._build_action_satisfied(action)

    monkeypatch.setattr(executor, "_owned_progress_counts", lambda *_args: (1, 0, 0))
    assert scheduler._build_action_satisfied(action)
