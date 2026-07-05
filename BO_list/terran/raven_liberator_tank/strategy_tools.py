"""Resource-free tool package for the raven_liberator_tank strategy."""

from sc2.ids.unit_typeid import UnitTypeId
from sharpy.plans import BuildOrder, SequentialList
from sharpy.plans.acts import MineOpenBlockedBase
from sharpy.plans.build_step import Step
from sharpy.plans.require import All, Any, Supply, Time, UnitExists
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


class RavenLiberatorTankStrategyTools(BuildOrder):
    """Raven/liberator/tank tools that do not spend minerals, gas, or supply."""

    def __init__(self, attack_value: int = 35):
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
                    Any([
                        All([
                            UnitExists(UnitTypeId.RAVEN, 1, include_pending=True),
                            UnitExists(UnitTypeId.LIBERATOR, 4, include_pending=True),
                            UnitExists(UnitTypeId.VIKINGFIGHTER, 4, include_pending=True),
                            Supply(105),
                        ]),
                        All([
                            UnitExists(UnitTypeId.LIBERATOR, 4, include_pending=True),
                            UnitExists(UnitTypeId.VIKINGFIGHTER, 2, include_pending=True),
                            Time(10 * 60 + 30),
                        ]),
                    ]),
                    PlanZoneAttack(attack_value),
                ),
                PlanFinishEnemy(),
            ])
        )
