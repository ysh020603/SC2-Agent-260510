from sc2.ids.unit_typeid import UnitTypeId

from sharpy.managers.extensions.llm_observation_recorder import (
    llm_visible_unit_name,
)


def test_tactical_engine_forms_are_hidden_from_llm_context():
    assert llm_visible_unit_name(UnitTypeId.LIBERATORAG) == "LIBERATOR"
    assert llm_visible_unit_name(UnitTypeId.SUPPLYDEPOTLOWERED) == "SUPPLYDEPOT"
    assert llm_visible_unit_name(UnitTypeId.SIEGETANKSIEGED) == "SIEGETANK"
    assert llm_visible_unit_name(UnitTypeId.LURKERMPBURROWED) == "LURKERMP"
    assert llm_visible_unit_name(UnitTypeId.WARPPRISMPHASING) == "WARPPRISM"


def test_distinct_macro_entities_are_not_collapsed():
    assert llm_visible_unit_name(UnitTypeId.BARRACKSTECHLAB) == "BARRACKSTECHLAB"
    assert llm_visible_unit_name(UnitTypeId.OVERLORDTRANSPORT) == "OVERLORDTRANSPORT"
