"""Shared resource-free tactics for Zerg LLM strategy packages."""

from __future__ import annotations

from sharpy.plans import BuildOrder, SequentialList
from sharpy.plans.build_step import Step
from sharpy.plans.tactics import (
    DistributeWorkers,
    PlanCancelBuilding,
    PlanFinishEnemy,
    PlanZoneAttack,
    PlanZoneDefense,
    PlanZoneGather,
    SpeedMining,
)
from sharpy.plans.tactics.zerg import InjectLarva, OverlordScout, SpreadCreep
from dummies.zerg.worker_rush import WorkerAttack


def make_zerg_strategy_tools(
    *,
    attack_value: int = 20,
    worker_rush: bool = False,
    spread_creep: bool = True,
) -> BuildOrder:
    """Return tactics that never spend minerals, vespene, supply, or Larva."""
    tactics = [
        PlanCancelBuilding(),
        PlanZoneDefense(),
        OverlordScout(),
        InjectLarva(),
    ]
    if spread_creep:
        tactics.append(SpreadCreep())
    tactics.extend(
        [
            DistributeWorkers(),
            Step(None, SpeedMining(), lambda ai: ai.client.game_step > 5),
            PlanZoneGather(),
        ]
    )
    if worker_rush:
        tactics.append(WorkerAttack())
    tactics.extend(
        [
            PlanZoneAttack(attack_value),
            PlanFinishEnemy(),
        ]
    )
    return BuildOrder(SequentialList(tactics))


__all__ = ["make_zerg_strategy_tools"]
