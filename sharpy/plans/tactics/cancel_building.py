from sharpy.interfaces import IPreviousUnitsManager
from sharpy.plans.acts import ActBase
from sc2.unit import Unit
from sc2.constants import *

TOWNHALL_TYPES = {
    UnitTypeId.COMMANDCENTER,
    UnitTypeId.ORBITALCOMMAND,
    UnitTypeId.PLANETARYFORTRESS,
    UnitTypeId.NEXUS,
    UnitTypeId.HATCHERY,
    UnitTypeId.LAIR,
    UnitTypeId.HIVE,
}


class PlanCancelBuilding(ActBase):
    # Cancels a building when it's about to get destroyed
    def __init__(self):
        super().__init__()

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
        self.previous_units_manager = knowledge.get_required_manager(IPreviousUnitsManager)

    async def execute(self) -> bool:
        at_risk = []
        for building in self.ai.structures:  # type: Unit
            # Do not auto-cancel townhalls. In the LLM macro pipeline this caused
            # repeated "expand -> cancel damaged CC -> expand again" loops under
            # pressure, burning resources and keeping the scheduler non-drained.
            if building.type_id in TOWNHALL_TYPES:
                continue
            if 1 > building.build_progress > 0:
                if self.building_going_down(building):
                    at_risk.append(building)

        if not at_risk:
            return True

        # Some engine structures report 0 < build_progress < 1 but are not
        # cancellable construction jobs (notably a growing CreepTumor). Do
        # not infer command validity from build_progress: use SC2's live
        # available-ability surface before issuing the cancel.
        try:
            abilities_by_building = await self.ai.get_available_abilities(
                at_risk,
                ignore_resource_requirements=True,
            )
        except Exception:
            return True

        for building, abilities in zip(at_risk, abilities_by_building):
            if AbilityId.CANCEL_BUILDINPROGRESS not in abilities:
                continue
            self.print(
                f"Cancelled {building.type_id.name} at {building.position} with {building.health} health"
            )
            building(AbilityId.CANCEL_BUILDINPROGRESS)
        return True

    def building_going_down(self, building: Unit) -> bool:
        """Returns boolean indicating whether a building is low on health and under attack."""
        previous_building = self.previous_units_manager.last_unit(building.tag)
        if previous_building:
            health = building.health
            compare_health = max(70, building.health_max * 0.09)
            if health < previous_building.health < compare_health:
                return True
        return False
