"""Resource-free tool package for the yamato_rust_fleet strategy.

Derived from ``dummies/terran/yamato_rust_fleet.py``. Resource-spending tools
such as ``Repair`` are intentionally omitted. The original random attack
threshold ``random.randint(50, 80)`` is fixed to its lowest value, ``50``. The
build-choice candidate is fixed to the jump branch, so ``TacticalJumpIn`` is
always enabled.
"""

from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sharpy.plans import BuildOrder, SequentialList
from sharpy.plans.acts import ActBase, MineOpenBlockedBase
from sharpy.plans.build_step import Step
from sharpy.plans.require import Time, UnitExists
from sharpy.plans.tactics import (
    DistributeWorkers,
    PlanCancelBuilding,
    PlanFinishEnemy,
    PlanZoneAttack,
    PlanZoneDefense,
    SpeedMining,
    WorkerScout,
)
from sharpy.plans.tactics.terran import (
    CallMule,
    ContinueBuilding,
    LowerDepots,
    ManTheBunkers,
    PlanZoneGatherTerran,
    ScanEnemy,
)
from SC2_Agent.prompt_context import terran_automation_profile


AUTOMATION_PROFILE = terran_automation_profile(
    strategy="yamato_rust_fleet",
    attack_threshold=50,
    special_behaviors=(
        "Once more than one Battlecruiser exists, TacticalJumpIn orders all "
        "Battlecruisers to tactical-jump behind the enemy main exactly once.",
        "Worker distribution uses a four-worker gas weighting for this gas-heavy fleet.",
    ),
)


class TacticalJumpIn(ActBase):
    """Warp ready Battlecruisers behind the enemy main once."""

    def __init__(self):
        self.done = False
        super().__init__()

    async def execute(self) -> bool:
        if self.done:
            return True
        bcs = self.cache.own(UnitTypeId.BATTLECRUISER)
        if bcs.amount > 1:
            self.done = True
            jump_target = self.zone_manager.enemy_main_zone.behind_mineral_position_center
            for bc in bcs:
                self.knowledge.cooldown_manager.used_ability(bc.tag, AbilityId.EFFECT_TACTICALJUMP)
                bc(AbilityId.EFFECT_TACTICALJUMP, jump_target)
        return True


class YamatoRustFleetStrategyTools(BuildOrder):
    """Yamato rust fleet tools that do not spend minerals, gas, or supply."""

    def __init__(self, attack_value: int = AUTOMATION_PROFILE.attack_threshold):
        super().__init__(
            SequentialList([
                MineOpenBlockedBase(),
                PlanCancelBuilding(),
                LowerDepots(),
                PlanZoneDefense(),
                Step(None, WorkerScout(), skip_until=UnitExists(UnitTypeId.SUPPLYDEPOT, 1)),
                Step(None, CallMule(50), skip=Time(5 * 60)),
                Step(None, CallMule(100), skip_until=Time(5 * 60)),
                Step(None, ScanEnemy(), skip_until=Time(5 * 60)),
                DistributeWorkers(4),
                Step(None, SpeedMining(), lambda ai: ai.client.game_step > 5),
                ManTheBunkers(),
                ContinueBuilding(),
                PlanZoneGatherTerran(),
                Step(None, TacticalJumpIn()),
                Step(None, PlanZoneAttack(attack_value)),
                PlanFinishEnemy(),
            ])
        )
