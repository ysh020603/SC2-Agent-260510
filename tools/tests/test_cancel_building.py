import asyncio
from types import SimpleNamespace

from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId

from sharpy.plans.tactics import PlanCancelBuilding


class _Building(SimpleNamespace):
    def __call__(self, ability):
        self.issued.append(ability)


def _building(unit_type, tag):
    return _Building(
        type_id=unit_type,
        tag=tag,
        build_progress=0.5,
        health=20,
        health_max=1000,
        position=SimpleNamespace(),
        issued=[],
    )


def test_cancel_building_uses_live_engine_ability():
    barracks = _building(UnitTypeId.BARRACKS, 1)
    creep_tumor = _building(UnitTypeId.CREEPTUMOR, 2)
    previous = {
        1: SimpleNamespace(health=30),
        2: SimpleNamespace(health=30),
    }

    async def available(buildings, ignore_resource_requirements):
        assert buildings == [barracks, creep_tumor]
        assert ignore_resource_requirements
        return [[AbilityId.CANCEL_BUILDINPROGRESS], []]

    act = PlanCancelBuilding()
    act.ai = SimpleNamespace(
        structures=[barracks, creep_tumor],
        get_available_abilities=available,
    )
    act.previous_units_manager = SimpleNamespace(
        last_unit=lambda tag: previous[tag],
    )
    act.print = lambda *_args, **_kwargs: None

    assert asyncio.run(act.execute())
    assert barracks.issued == [AbilityId.CANCEL_BUILDINPROGRESS]
    assert creep_tumor.issued == []
