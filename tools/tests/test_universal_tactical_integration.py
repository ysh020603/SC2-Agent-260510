import inspect
import json
from pathlib import Path

import pytest
from sc2.data import Race
from sc2.ids.unit_typeid import UnitTypeId

from sharpy.combat import GenericMicro
from sharpy.combat.micro_rules import MicroRules
from sharpy.combat.protoss import MicroStalkers
from sharpy.combat.terran import MicroBattleCruisers, MicroBio, MicroTanks
from sharpy.combat.zerg import MicroLurkers
from sharpy.plans.tactics import PlanZoneAttack, PlanZoneDefense

from SC2_Agent.universal_tactics import AdaptiveZoneAttack, create_universal_tactical_plan
from SC2_Agent.universal_tactics.config import DEFAULT_CONFIG
from SC2_Agent.universal_tactics.universal_plan import UNIVERSAL_TACTICAL_PROFILE


ROOT = Path(__file__).resolve().parents[2]


def walk_plan(item):
    yield item
    for attr in ("orders",):
        for child in getattr(item, attr, ()):
            yield from walk_plan(child)
    action = getattr(item, "action", None)
    if action is not None:
        yield from walk_plan(action)


@pytest.mark.parametrize("race", [Race.Terran, Race.Protoss, Race.Zerg])
def test_every_race_uses_one_adaptive_attack_and_defense(race):
    nodes = list(walk_plan(create_universal_tactical_plan(race)))
    adaptive = [node for node in nodes if isinstance(node, AdaptiveZoneAttack)]
    defense = [node for node in nodes if isinstance(node, PlanZoneDefense)]
    assert len(adaptive) == 1
    assert len(defense) == 1
    assert adaptive[0].start_attack_power == DEFAULT_CONFIG.global_min_attack_power


def test_adaptive_attack_inherits_existing_micro_and_retreat_state_machine():
    assert AdaptiveZoneAttack.handle_attack is PlanZoneAttack.handle_attack
    assert AdaptiveZoneAttack._should_retreat is PlanZoneAttack._should_retreat
    assert AdaptiveZoneAttack._get_target is PlanZoneAttack._get_target


def test_existing_unit_micro_registry_remains_the_combat_backend():
    rules = MicroRules()
    rules.load_default_micro()
    assert isinstance(rules.unit_micros[UnitTypeId.MARINE], MicroBio)
    assert isinstance(rules.unit_micros[UnitTypeId.MARAUDER], MicroBio)
    assert isinstance(rules.unit_micros[UnitTypeId.SIEGETANK], MicroTanks)
    assert isinstance(rules.unit_micros[UnitTypeId.BATTLECRUISER], MicroBattleCruisers)
    assert isinstance(rules.unit_micros[UnitTypeId.STALKER], MicroStalkers)
    assert isinstance(rules.unit_micros[UnitTypeId.LURKERMP], MicroLurkers)
    assert isinstance(rules.generic_micro, GenericMicro)


def test_gather_and_defense_do_not_block_adaptive_attack():
    from sharpy.plans.tactics import PlanZoneGather
    from sharpy.plans.tactics.terran import PlanZoneGatherTerran

    assert "return True" in inspect.getsource(PlanZoneDefense.execute)
    assert "return True" in inspect.getsource(PlanZoneGather.execute)
    assert "return True" in inspect.getsource(PlanZoneGatherTerran.execute)


def test_live_bots_do_not_import_strategy_tools_or_profiles():
    source = (ROOT / "dummies" / "generic" / "universal_llm_bot.py").read_text(encoding="utf-8")
    assert "_load_strategy_tools" not in source
    assert ".strategy_tools" not in source
    assert "AUTOMATION_PROFILE" not in source
    assert "_load_universal_tactical_tools" in source

    human_source = (
        ROOT / "dummies" / "generic" / "universal_llm_human_skill_bot.py"
    ).read_text(encoding="utf-8")
    assert "_load_strategy_tools" not in human_source
    assert ".strategy_tools" not in human_source
    assert "attack_threshold" not in human_source
    assert "attack_value" not in human_source
    assert "UNIVERSAL_TACTICAL_PROFILE" in human_source


def test_universal_profile_has_no_threshold_or_special_strategy_gate():
    lowered = UNIVERSAL_TACTICAL_PROFILE.lower()
    assert "attack threshold" not in lowered
    assert "strategy-specific" not in lowered
    assert "army cohesion" in lowered


def test_frozen_json_matches_runtime_config():
    frozen = json.loads((ROOT / "UNIVERSAL_TACTICS_V1_CONFIG.json").read_text(encoding="utf-8"))
    assert frozen == DEFAULT_CONFIG.as_dict()
    assert len(DEFAULT_CONFIG.stable_hash()) == 64

    baseline_manifest = json.loads(
        (ROOT / "READABLE_SKILL_BASELINE_MANIFEST.json").read_text(encoding="utf-8")
    )
    automation = baseline_manifest["strategy_automation"]
    assert automation["profile"] == "universal_tactical_controller_v1"
    assert automation["shared_across_all_six_variants"] is True
    assert automation["skill_specific_attack_thresholds"] is False
    assert automation["config_sha256"] == DEFAULT_CONFIG.stable_hash()


def test_controller_source_has_no_routing_dimensions_or_unit_gates():
    from SC2_Agent.universal_tactics.controller import UniversalTacticalController
    from SC2_Agent.universal_tactics import readiness

    source = inspect.getsource(UniversalTacticalController) + inspect.getsource(readiness)
    for forbidden in ("skill_id", "opening_id", "ablation_method", "SIEGETANK", "LURKER", "STIMPACK"):
        assert forbidden not in source
