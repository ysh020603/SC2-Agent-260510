import asyncio
from types import SimpleNamespace

from dummies.generic.universal_llm_bot import UniversalLLMBot
from sc2.action import combine_actions
from sc2.constants import COMBINEABLE_ABILITIES
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit_command import UnitCommand
from SC2_Agent.data_tools import action_candidates_for_entity
from SC2_Agent.execution.command import DONE, PENDING, RUNNING, WAITING, PlannedAction
from SC2_Agent.execution.producer_selector import candidate_producers, choose_producer
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


def test_pending_upgrade_id_is_an_engine_commit_boundary(monkeypatch):
    upgrade = object()
    action = PlannedAction(
        action_name="CYBERNETICSCORERESEARCH_PROTOSSAIRWEAPONSLEVEL1",
        category="research",
        canonical_name="ProtossAirWeaponsLevel1",
        target_result="ProtossAirWeaponsLevel1",
        queue_id=6,
        queue_position=1,
    )
    scheduler = ExecutionScheduler()
    scheduler.ai = SimpleNamespace(
        time=100.0,
        state=SimpleNamespace(upgrades=set()),
        structures=[],
        already_pending_upgrade=lambda candidate: 0.25 if candidate is upgrade else 0,
    )
    scheduler.actions = [action]
    monkeypatch.setattr(
        "SC2_Agent.execution.scheduler.mapping.upgrade_for",
        lambda _name: upgrade,
    )

    assert scheduler.uncommitted_canonical_names() == []
    assert action.state == DONE
    assert action.issued_count == 1


def test_gas_build_waits_for_a_free_geyser_instead_of_being_abandoned():
    action = PlannedAction(
        action_name="PROTOSSBUILD_ASSIMILATOR",
        category="build",
        canonical_name="Assimilator",
        target_result="Assimilator",
        state=RUNNING,
        running_start_time=0.0,
    )
    scheduler = ExecutionScheduler(running_abandon_sec=25.0)
    scheduler.actions = [action]

    scheduler._abandon_stuck_running(now=30.0)

    assert action.state == WAITING
    assert scheduler.waiter is action
    assert action not in scheduler.actions


def test_technology_structure_target_count_is_capped(monkeypatch):
    scheduler = ExecutionScheduler()
    monkeypatch.setattr(scheduler, "_equivalent_existing_count", lambda _unit_type: 1)

    evolution_chambers = PlannedAction(
        action_name="ZERGBUILD_EVOLUTIONCHAMBER",
        category="build",
        canonical_name="EvolutionChamber",
        target_result="EvolutionChamber",
        quantity=4,
    )
    assert scheduler._compute_build_to_count(evolution_chambers) == 2

    cybernetics_cores = PlannedAction(
        action_name="PROTOSSBUILD_CYBERNETICSCORE",
        category="build",
        canonical_name="CyberneticsCore",
        target_result="CyberneticsCore",
        quantity=3,
    )
    monkeypatch.setattr(
        "SC2_Agent.execution.scheduler.mapping.unit_type_for",
        lambda name: {
            "EvolutionChamber": UnitTypeId.EVOLUTIONCHAMBER,
            "CyberneticsCore": UnitTypeId.CYBERNETICSCORE,
        }.get(name),
    )
    assert scheduler._compute_build_to_count(cybernetics_cores) == 1


def test_producer_selection_is_deterministic_and_prefers_idle():
    busy = SimpleNamespace(is_idle=False, orders=[1], tag=1)
    idle_high_tag = SimpleNamespace(is_idle=True, orders=[], tag=9)
    idle_low_tag = SimpleNamespace(is_idle=True, orders=[], tag=3)
    selected = choose_producer(
        [(busy, "busy"), (idle_high_tag, "idle"), (idle_low_tag, "idle")]
    )
    assert selected is idle_low_tag


def test_producer_candidates_exclude_units_already_commanded_this_frame():
    already_used = SimpleNamespace(
        build_progress=1.0,
        is_constructing_scv=False,
        is_idle=True,
        orders=[],
        tag=1,
    )
    available = SimpleNamespace(
        build_progress=1.0,
        is_constructing_scv=False,
        is_idle=True,
        orders=[],
        tag=2,
    )

    async def get_available_abilities(units, ignore_resource_requirements):
        assert ignore_resource_requirements
        assert units == [available]
        return [[AbilityId.GATEWAYTRAIN_STALKER]]

    ai = SimpleNamespace(
        units=[],
        structures=[already_used, available],
        unit_tags_received_action={1},
        get_available_abilities=get_available_abilities,
    )
    result = asyncio.run(candidate_producers(ai, AbilityId.GATEWAYTRAIN_STALKER))
    assert result == [(available, "idle")]


def test_scheduler_keeps_all_reviewed_gateway_action_candidates():
    candidates = action_candidates_for_entity("protoss", "Stalker")
    scheduler = ExecutionScheduler()
    scheduler.replace_uncommitted_queue(
        [("Stalker", candidates[0], tuple(candidates[1:]))],
        queue_id=9,
    )
    action = scheduler.actions[0]
    assert action.canonical_name == "Stalker"
    assert action.execution_mode == "train"
    assert set(action._candidate_specs) == {
        row.ability_name for row in candidates
    }


def test_gateway_action_switches_to_warp_in_when_only_warpgate_is_ready(monkeypatch):
    candidates = action_candidates_for_entity("protoss", "Stalker")
    scheduler = ExecutionScheduler()
    scheduler.ai = SimpleNamespace()
    scheduler.replace_uncommitted_queue(
        [("Stalker", candidates[0], tuple(candidates[1:]))],
        queue_id=10,
    )
    action = scheduler.actions[0]

    async def candidates_for_ability(_ai, ability):
        if ability == AbilityId.WARPGATETRAIN_STALKER:
            return [(SimpleNamespace(tag=7), "idle")]
        if ability == AbilityId.GATEWAYTRAIN_STALKER:
            return [(SimpleNamespace(tag=8), "idle")]
        return []

    monkeypatch.setattr(
        "SC2_Agent.execution.scheduler.is_available_now",
        lambda _ai, _action: True,
    )
    monkeypatch.setattr(
        "SC2_Agent.execution.scheduler.producer_selector.candidate_producers",
        candidates_for_ability,
    )
    asyncio.run(scheduler._select_runtime_action_with_producer(action))

    assert action.action_name == "WARPGATETRAIN_STALKER"
    assert action.execution_mode == "warp_in"


def test_archon_commands_are_combined_into_one_two_templar_engine_action():
    assert AbilityId.MORPH_ARCHON in COMBINEABLE_ABILITIES
    fake_unit_type = type("Unit", (), {})
    first = fake_unit_type()
    first.tag = 101
    second = fake_unit_type()
    second.tag = 202
    commands = [
        UnitCommand(AbilityId.MORPH_ARCHON, first),
        UnitCommand(AbilityId.MORPH_ARCHON, second),
    ]
    actions = list(combine_actions(commands))

    assert len(actions) == 1
    assert set(actions[0].unit_command.unit_tags) == {101, 202}
