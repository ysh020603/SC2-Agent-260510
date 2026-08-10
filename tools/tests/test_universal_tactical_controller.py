from dataclasses import replace

import pytest

from sharpy.managers.extensions.game_states.advantage import Advantage

from SC2_Agent.universal_tactics import (
    BattleSnapshot,
    TacticalPosture,
    UniversalTacticalController,
)
from SC2_Agent.universal_tactics.config import UniversalTacticalConfig
from SC2_Agent.universal_tactics.validation import assert_cross_context_invariance


def snapshot(**changes):
    base = BattleSnapshot(
        game_time=420,
        own_total_power=24,
        enemy_known_power=10,
        enemy_predicted_power=12,
        own_ground_power=24,
        own_air_power=10,
        own_ground_presence=24,
        enemy_ground_presence=10,
        enemy_air_presence=2,
        own_detector_count=1,
        predicted_army_advantage=Advantage.ClearAdvantage,
        income_advantage=Advantage.Even,
        supply_used=120,
        supply_cap=200,
        army_supply=60,
        largest_army_group_power=20,
        largest_army_group_fraction=0.82,
    )
    return replace(base, **changes)


def posture(state):
    return UniversalTacticalController().decide_posture(state)


def test_clear_advantage_attacks():
    assert posture(snapshot()) == TacticalPosture.ATTACK


def test_defense_has_priority_over_clear_advantage():
    assert posture(snapshot(threatened_zone_count=1)) == TacticalPosture.DEFEND


def test_global_floor_and_cohesion_gather():
    assert posture(snapshot(own_total_power=5.9)) == TacticalPosture.GATHER
    assert posture(snapshot(largest_army_group_fraction=0.71)) == TacticalPosture.GATHER


def test_air_heavy_enemy_blocks_ground_only_army():
    state = snapshot(
        own_total_power=50,
        own_ground_power=50,
        own_air_power=2,
        enemy_predicted_power=20,
        enemy_air_presence=15,
        enemy_ground_presence=5,
    )
    assert posture(state) == TacticalPosture.GATHER


def test_ground_coverage_gate():
    state = snapshot(
        own_total_power=50,
        own_ground_power=3,
        own_air_power=30,
        enemy_predicted_power=20,
        enemy_ground_presence=18,
        enemy_air_presence=2,
    )
    assert posture(state) == TacticalPosture.GATHER


def test_detection_gate_and_defense_override():
    state = snapshot(enemy_stealth_power=8, own_detector_count=0)
    assert posture(state) == TacticalPosture.GATHER
    assert posture(replace(state, threatened_zone_count=1)) == TacticalPosture.DEFEND


def test_economic_timing_window_attacks():
    state = snapshot(
        predicted_army_advantage=Advantage.SmallAdvantage,
        income_advantage=Advantage.ClearDisadvantage,
    )
    assert posture(state) == TacticalPosture.ATTACK


def test_economic_greed_does_not_force_attack():
    state = snapshot(
        predicted_army_advantage=Advantage.SmallDisadvantage,
        income_advantage=Advantage.ClearAdvantage,
    )
    assert posture(state) == TacticalPosture.GATHER


def test_near_max_supply_attacks_when_safe():
    state = snapshot(
        predicted_army_advantage=Advantage.Even,
        income_advantage=Advantage.Even,
        supply_used=195,
    )
    assert posture(state) == TacticalPosture.ATTACK


@pytest.mark.parametrize(
    "composition",
    [
        "terran_bio",
        "terran_tank",
        "terran_battlecruiser",
        "protoss_stalker",
        "protoss_mixed_ground",
        "zerg_roach_hydra",
        "zerg_lurker",
    ],
)
def test_unit_compositions_share_readiness_without_unit_gates(composition):
    assert posture(snapshot()) == TacticalPosture.ATTACK


def test_retreat_cooldown_and_posture_hysteresis():
    controller = UniversalTacticalController()
    controller.note_retreat(400)
    assert controller.decide_posture(snapshot(game_time=405)) == TacticalPosture.GATHER
    assert controller.decide_posture(snapshot(game_time=413)) == TacticalPosture.ATTACK

    controller = UniversalTacticalController()
    assert controller.decide_posture(snapshot(game_time=100)) == TacticalPosture.ATTACK
    weaker = snapshot(
        game_time=105,
        predicted_army_advantage=Advantage.Even,
        income_advantage=Advantage.Even,
    )
    assert controller.decide_posture(weaker) == TacticalPosture.ATTACK
    assert controller.decide_posture(replace(weaker, game_time=116)) == TacticalPosture.GATHER


def test_cross_skill_opening_ablation_invariance():
    contexts = [
        {"skill_id": "PvP_O01", "opening_id": "one", "ablation_method": "full"},
        {"skill_id": "TvZ_O99", "opening_id": "two", "ablation_method": "positive_only"},
        {"skill_id": "ZvT_O02", "opening_id": "three", "ablation_method": "frequency_only"},
    ]
    assert assert_cross_context_invariance(snapshot(), contexts) == TacticalPosture.ATTACK


def test_abstract_readiness_is_race_invariant():
    contexts = [{"race": race} for race in ("terran", "protoss", "zerg")]
    assert assert_cross_context_invariance(snapshot(), contexts) == TacticalPosture.ATTACK


def test_global_config_is_frozen_and_has_no_routing_fields():
    config = UniversalTacticalConfig()
    with pytest.raises(Exception):
        config.min_cohesion_to_attack = 0.5
    assert not ({"skill_id", "opening_id", "ablation_method"} & set(config.as_dict()))
