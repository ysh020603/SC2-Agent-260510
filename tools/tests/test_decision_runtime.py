from types import SimpleNamespace

from dummies.generic.universal_llm_bot import UniversalLLMBot
from SC2_Agent.execution.command import DONE, PENDING, RUNNING, PlannedAction
from SC2_Agent.execution.producer_selector import choose_producer
from SC2_Agent.execution.scheduler import ExecutionScheduler


def _trigger_bot():
    bot = UniversalLLMBot.__new__(UniversalLLMBot)
    bot._decision_cycle_count = 1
    bot._last_decision_time = 0.0
    bot.decision_interval_seconds = 60.0
    bot._queue_had_work_since_decision = True
    bot._last_drained_state = False
    return bot


def test_trigger_waits_when_one_uncommitted_task_remains():
    bot = _trigger_bot()
    assert bot._decision_trigger(now=30.0, drained=False) is None
    assert bot._decision_trigger(now=60.0, drained=False) == "interval_elapsed"


def test_trigger_fires_when_nonempty_queue_transitions_to_drained():
    bot = _trigger_bot()
    assert bot._decision_trigger(now=10.0, drained=True) == "queue_drained"


def test_empty_decision_does_not_immediately_retrigger():
    bot = _trigger_bot()
    bot._queue_had_work_since_decision = False
    assert bot._decision_trigger(now=10.0, drained=True) is None
    assert bot._decision_trigger(now=60.0, drained=True) == "interval_elapsed"


def test_uncommitted_names_exclude_issued_copies_and_terminal_work():
    scheduler = ExecutionScheduler()
    partial = PlannedAction(
        action_name="BARRACKSTRAIN_MARINE",
        category="train",
        canonical_name="Marine",
        queue_id=2,
        queue_position=2,
        quantity=4,
        issued_count=2,
        state=RUNNING,
    )
    pending = PlannedAction(
        action_name="TERRANBUILD_FACTORY",
        category="build",
        canonical_name="Factory",
        queue_id=2,
        queue_position=1,
        state=PENDING,
    )
    committed = PlannedAction(
        action_name="TERRANBUILD_STARPORT",
        category="build",
        canonical_name="Starport",
        queue_id=2,
        queue_position=3,
        quantity=1,
        issued_count=1,
        state=DONE,
    )
    scheduler.actions = [partial, committed, pending]

    assert scheduler.uncommitted_canonical_names() == [
        "Factory",
        "Marine",
        "Marine",
    ]


def test_new_decision_atomically_replaces_uncommitted_queue():
    scheduler = ExecutionScheduler()
    scheduler.actions = [
        PlannedAction(
            action_name="TERRANBUILD_BARRACKS",
            category="build",
            canonical_name="Barracks",
            queue_id=1,
            queue_position=1,
        ),
        PlannedAction(
            action_name="BARRACKSTRAIN_MARINE",
            category="train",
            canonical_name="Marine",
            queue_id=1,
            queue_position=2,
        ),
    ]

    replaced = scheduler.replace_uncommitted_queue(
        [
            ("SupplyDepot", "TERRANBUILD_SUPPLYDEPOT"),
            ("Factory", "TERRANBUILD_FACTORY"),
        ],
        queue_id=2,
    )

    assert replaced == ["Barracks", "Marine"]
    assert scheduler.uncommitted_canonical_names() == ["SupplyDepot", "Factory"]
    assert [(pa.queue_id, pa.queue_position) for pa in scheduler.actions] == [
        (2, 1),
        (2, 2),
    ]
    assert scheduler.waiter is None


def test_waiter_returns_to_its_original_model_position():
    scheduler = ExecutionScheduler()
    first = PlannedAction(
        action_name="TERRANBUILD_BARRACKS",
        category="build",
        canonical_name="Barracks",
        queue_id=4,
        queue_position=1,
    )
    second = PlannedAction(
        action_name="TERRANBUILD_SUPPLYDEPOT",
        category="build",
        canonical_name="SupplyDepot",
        queue_id=4,
        queue_position=2,
    )
    scheduler.actions = [second]
    scheduler.waiter = first

    scheduler._release_waiter_back_to_actions(first)

    assert scheduler.actions == [first, second]
    assert scheduler.waiter is None


def test_research_order_is_an_engine_commit_boundary():
    ability = SimpleNamespace(name="RESEARCH_STIMPACK")
    action = PlannedAction(
        action_name="BARRACKSTECHLABRESEARCH_STIMPACK",
        category="research",
        canonical_name="Stimpack",
        ability=ability,
        queue_id=5,
        queue_position=1,
    )
    matching_order = SimpleNamespace(ability=SimpleNamespace(id=ability))
    scheduler = ExecutionScheduler()
    scheduler.ai = SimpleNamespace(
        time=100.0,
        state=SimpleNamespace(upgrades=set()),
        structures=[SimpleNamespace(orders=[matching_order])],
    )
    scheduler.actions = [action]

    assert scheduler.uncommitted_canonical_names() == []
    assert action.state == DONE
    assert action.issued_count == 1


def test_producer_selection_is_deterministic_and_prefers_idle():
    busy = SimpleNamespace(is_idle=False, orders=[1], tag=1)
    idle_high_tag = SimpleNamespace(is_idle=True, orders=[], tag=9)
    idle_low_tag = SimpleNamespace(is_idle=True, orders=[], tag=3)
    selected = choose_producer(
        [(busy, "busy"), (idle_high_tag, "idle"), (idle_low_tag, "idle")]
    )
    assert selected is idle_low_tag
