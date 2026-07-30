"""Resource-free tool package for the blueflame_locks strategy.

Derived from ``dummies/terran/blueflame_locks.py``. Resource-spending tools such
as ``Repair`` are intentionally omitted. The attack threshold keeps its original
fixed value, ``50``, and its original gating condition is preserved.
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
from SC2_Agent.prompt_context import terran_automation_profile


AUTOMATION_PROFILE = terran_automation_profile(
    strategy="blueflame_locks",
    attack_threshold=50,
    attack_gate=(
        "The attack is additionally gated until any one condition is true: "
        "Cyclone lock-on damage research is at least 95% complete and 6 Cyclones "
        "exist/include pending; or 2 Thors and 8 Cyclones exist/include pending; "
        "or game time reaches 10:00."
    ),
)


class BlueflameLocksStrategyTools(BuildOrder):
    """Blueflame locks tools that do not spend minerals, gas, or supply."""

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
                DistributeWorkers(),
                Step(None, SpeedMining(), lambda ai: ai.client.game_step > 5),
                ManTheBunkers(),
                ContinueBuilding(),
                PlanZoneGatherTerran(),
                Step(
                    Any([
                        All([
                            TechReady(UpgradeId.CYCLONELOCKONDAMAGEUPGRADE, 0.95),
                            UnitExists(UnitTypeId.CYCLONE, 6, include_pending=True),
                        ]),
                        All([
                            UnitExists(UnitTypeId.THOR, 2, include_pending=True),
                            UnitExists(UnitTypeId.CYCLONE, 8, include_pending=True),
                        ]),
                        Time(10 * 60),
                    ]),
                    PlanZoneAttack(attack_value),
                ),
                PlanFinishEnemy(),
            ])
        )
