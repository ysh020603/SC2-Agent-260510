"""Resource-free tool package for the two_base_matrix_tanks strategy.

Derived from ``dummies/terran/two_base_matrix_tanks.py``. Resource-spending
tools such as ``Repair`` are intentionally omitted. The attack threshold keeps
its original fixed value, ``60``, and its original gating condition is
preserved.
"""

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


class TwoBaseMatrixTanksStrategyTools(BuildOrder):
    """Two-base matrix tank tools that do not spend minerals, gas, or supply."""

    def __init__(self, attack_value: int = 60):
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
                            TechReady(UpgradeId.STIMPACK, 0.9),
                            UnitExists(UnitTypeId.SIEGETANK, 4, include_pending=True),
                            UnitExists(UnitTypeId.RAVEN, 1, include_pending=True),
                        ]),
                        All([
                            UnitExists(UnitTypeId.SIEGETANK, 6, include_pending=True),
                            Time(9 * 60),
                        ]),
                    ]),
                    PlanZoneAttack(attack_value),
                ),
                PlanFinishEnemy(),
            ])
        )
