# Starts all out attack with workers on specified unit supply that is not workers
import random

from sharpy.managers.core.roles import UnitTask
from sharpy.plans.acts import ActBase
from sc2.unit import Unit


# Plan that blocks any further strategies until an all-out attack has been started and ended
class PlanFinishEnemy(ActBase):
    def __init__(self):
        super().__init__()

    async def execute(self):
        target = await self.find_attack_position(self.ai)
        # PlanZoneGather runs immediately before this tactic in the shared
        # strategy tool chains.  It may have issued a move command to units
        # that are still in the role manager's Idle role, so BotAI's
        # ``units.idle`` view is too narrow here and can leave an entire army
        # gathering forever when the last enemy structure is out of vision.
        #
        # PlanFinishEnemy is reached only after PlanZoneAttack reports that it
        # has no known target.  At that point it is correct for the final
        # search order to supersede the gather order for role-idle combat
        # units.
        for unit in self.roles.idle:  # type: Unit
            if self.unit_values.should_attack(unit):
                unit.attack(target)
                self.roles.set_task(UnitTask.Attacking, unit)

        # Refresh roles
        units = self.roles.all_from_task(UnitTask.Attacking)
        self.roles.refresh_tasks(units)

        return True

    async def find_attack_position(self, ai):
        main_pos = self.zone_manager.own_main_zone.center_location

        target = random.choice(list(ai.expansion_locations_list))
        last_distance2 = target.distance_to(main_pos)
        target_known = False
        if ai.enemy_structures.exists:
            for building in ai.enemy_structures:
                if building.health > 0:
                    current_distance2 = target.distance_to(main_pos)
                    if not target_known or current_distance2 < last_distance2:
                        target = building.position
                        last_distance2 = current_distance2
                        target_known = True
        return target
