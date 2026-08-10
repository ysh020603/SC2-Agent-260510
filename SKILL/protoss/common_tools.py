"""Shared resource-free tactics for Protoss LLM strategy packages."""

from __future__ import annotations

from sc2.ids.unit_typeid import UnitTypeId

from sharpy.plans import BuildOrder, SequentialList
from sharpy.plans.acts import MorphWarpGates
from sharpy.plans.acts.protoss import ChronoAnyTech, ChronoBuilding
from sharpy.plans.build_step import Step
from sharpy.plans.tactics import (
    DistributeWorkers,
    PlanCancelBuilding,
    PlanFinishEnemy,
    PlanZoneAttack,
    PlanZoneDefense,
    PlanZoneGather,
    SpeedMining,
    WorkerScout,
)


def make_protoss_strategy_tools(*, attack_value: int = 16) -> BuildOrder:
    """Return tactics that do not spend minerals, vespene, or supply."""
    return BuildOrder(
        SequentialList(
            [
                PlanCancelBuilding(),
                PlanZoneDefense(),
                WorkerScout(),
                ChronoAnyTech(0),
                ChronoBuilding(UnitTypeId.NEXUS, 10_000),
                ChronoBuilding(UnitTypeId.GATEWAY, 10_000),
                ChronoBuilding(UnitTypeId.ROBOTICSFACILITY, 10_000),
                ChronoBuilding(UnitTypeId.STARGATE, 10_000),
                MorphWarpGates(),
                DistributeWorkers(),
                Step(None, SpeedMining(), lambda ai: ai.client.game_step > 5),
                PlanZoneGather(),
                PlanZoneAttack(attack_value),
                PlanFinishEnemy(),
            ]
        )
    )


__all__ = ["make_protoss_strategy_tools"]
