"""Resource-free tool package for the safe_211_mine strategy."""

from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sharpy.plans import BuildOrder, SequentialList
from sharpy.plans.acts import MineOpenBlockedBase
from sharpy.plans.build_step import Step
from sharpy.plans.require import All, Any, TechReady, Time, UnitExists
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


class Safe211MineStrategyTools(BuildOrder):
    """Safe 2-1-1 mine tools that do not spend minerals, gas, or supply."""

    def __init__(self, attack_value: int = 25):
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
                DistributeWorkers(),
                Step(None, SpeedMining(), lambda ai: ai.client.game_step > 5),
                ManTheBunkers(),
                ContinueBuilding(),
                PlanZoneGatherTerran(),
                Step(
                    All([
                        Any([TechReady(UpgradeId.STIMPACK, 0.7), Time(6 * 60 + 30)]),
                        UnitExists(UnitTypeId.MARINE, 36, include_pending=True),
                        UnitExists(UnitTypeId.WIDOWMINE, 4, include_pending=True),
                        UnitExists(UnitTypeId.MEDIVAC, 2, include_pending=True),
                    ]),
                    PlanZoneAttack(attack_value),
                ),
                PlanFinishEnemy(),
            ])
        )
