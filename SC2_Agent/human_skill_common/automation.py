"""Race-generic, resource-free tactical automation shared by every variant."""

from __future__ import annotations

from sharpy.plans import BuildOrder, SequentialList
from sharpy.plans.acts import MineOpenBlockedBase
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
from sc2.ids.unit_typeid import UnitTypeId


def make_terran_generic_tools(*, attack_value: int = 18) -> BuildOrder:
    return BuildOrder(
        SequentialList(
            [
                MineOpenBlockedBase(),
                PlanCancelBuilding(),
                LowerDepots(),
                PlanZoneDefense(),
                Step(None, WorkerScout(), skip_until=UnitExists(UnitTypeId.SUPPLYDEPOT, 1)),
                Step(None, CallMule(50), skip=Time(5 * 60)),
                Step(None, CallMule(100), skip_until=Time(5 * 60)),
                Step(None, ScanEnemy(), skip_until=Time(5 * 60)),
                DistributeWorkers(),
                Step(None, SpeedMining(), lambda ai: ai.client.game_step > 5),
                ManTheBunkers(),
                ContinueBuilding(),
                PlanZoneGatherTerran(),
                PlanZoneAttack(attack_value),
                PlanFinishEnemy(),
            ]
        )
    )


__all__ = ["make_terran_generic_tools"]
