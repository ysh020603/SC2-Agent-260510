from SC2_Agent.data_tools import (
    action_candidates_for_entity,
    canonical_entity_name,
    is_known_race_entity,
    load_database,
    race_prompt_context,
    race_unit_names,
    race_upgrade_names,
)
from SC2_Agent.execution import mapping
from SC2_Agent.data_tools.obs_entities import collect_entities
from sc2.ids.upgrade_id import UpgradeId
from sharpy.plans.acts import BuildGas
from types import SimpleNamespace


def test_each_playable_race_has_a_complete_executable_catalog():
    for race in ("terran", "protoss", "zerg"):
        unit_names = race_unit_names(race)
        upgrade_names = race_upgrade_names(race)
        assert len(unit_names) >= 30
        assert len(upgrade_names) >= 20
        for name in unit_names:
            assert is_known_race_entity(race, name)
            assert mapping.unit_type_for(name) is not None
            candidates = action_candidates_for_entity(race, name)
            assert candidates
            assert all(mapping.ability_for(row.ability_name) is not None for row in candidates)
        for name in upgrade_names:
            assert is_known_race_entity(race, name)
            assert mapping.upgrade_for(name) is not None
            candidates = action_candidates_for_entity(race, name)
            assert candidates
            assert all(mapping.ability_for(row.ability_name) is not None for row in candidates)


def test_race_specific_execution_semantics_are_preserved():
    zerglings = action_candidates_for_entity("zerg", "Zergling")
    assert zerglings[0].ability_name == "LARVATRAIN_ZERGLING"
    assert zerglings[0].output_count == 2

    queen = action_candidates_for_entity("zerg", "Queen")
    assert queen[0].ability_name == "TRAINQUEEN_QUEEN"
    assert queen[0].execution_mode == "train"

    archon = action_candidates_for_entity("protoss", "Archon")
    assert archon[0].ability_name == "MORPH_ARCHON"
    assert archon[0].execution_mode == "paired_morph"

    stalker_modes = {
        row.execution_mode
        for row in action_candidates_for_entity("protoss", "Stalker")
    }
    assert {"train", "warp_in"} <= stalker_modes


def test_case_collision_does_not_hide_overlord_transport_unit():
    data = load_database()
    assert canonical_entity_name(data, "OverlordTransport") == "OverlordTransport"
    assert canonical_entity_name(data, "overlordtransport") == "overlordtransport"
    assert is_known_race_entity("zerg", "OverlordTransport")

    ai = SimpleNamespace(
        structures=[],
        units=[],
        state=SimpleNamespace(upgrades={UpgradeId.OVERLORDTRANSPORT}),
    )
    assert "overlordtransport" in collect_entities(ai)["completed"]


def test_prompt_context_names_the_correct_supply_provider():
    expected = {
        "terran": "Supply provider: SupplyDepot",
        "protoss": "Supply provider: Pylon",
        "zerg": "Supply provider: Overlord",
    }
    for race, line in expected.items():
        context = race_prompt_context(race)
        assert line in context
        for other_line in set(expected.values()) - {line}:
            assert other_line not in context


def test_all_three_gas_actions_use_the_race_aware_build_gas_act():
    actions = {
        "Refinery": "TERRANBUILD_REFINERY",
        "Assimilator": "PROTOSSBUILD_ASSIMILATOR",
        "Extractor": "ZERGBUILD_EXTRACTOR",
    }
    for target_result, action_name in actions.items():
        act = mapping.make_build_act(action_name, target_result, 1)
        assert isinstance(act, BuildGas)
