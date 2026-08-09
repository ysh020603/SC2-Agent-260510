"""Mechanic-only utilities selected by race, never by skill."""

from __future__ import annotations

from sc2.data import Race
from sc2.ids.unit_typeid import UnitTypeId

from sharpy.plans.acts import MineOpenBlockedBase, MorphWarpGates
from sharpy.plans.acts.protoss import ChronoAnyTech, ChronoBuilding
from sharpy.plans.build_step import Step
from sharpy.plans.require import Time
from sharpy.plans.tactics import (
    DistributeWorkers,
    PlanCancelBuilding,
    SpeedMining,
    WorkerScout,
)
from sharpy.plans.tactics.terran import (
    CallMule,
    ContinueBuilding,
    LowerDepots,
    ManTheBunkers,
    ScanEnemy,
)
from sharpy.plans.tactics.zerg import InjectLarva, OverlordScout, SpreadCreep


def _worker_economy_tools():
    return [
        DistributeWorkers(),
        Step(None, SpeedMining(), lambda ai: ai.client.game_step > 5),
    ]


def create_race_utility_tools(race: Race):
    if race == Race.Terran:
        return [
            MineOpenBlockedBase(),
            PlanCancelBuilding(),
            LowerDepots(),
            WorkerScout(),
            Step(None, CallMule(50), skip=Time(5 * 60)),
            Step(None, CallMule(100), skip_until=Time(5 * 60)),
            Step(None, ScanEnemy(), skip_until=Time(5 * 60)),
            *_worker_economy_tools(),
            ManTheBunkers(),
            ContinueBuilding(),
        ]
    if race == Race.Protoss:
        return [
            PlanCancelBuilding(),
            WorkerScout(),
            ChronoAnyTech(0),
            ChronoBuilding(UnitTypeId.NEXUS, 10_000),
            ChronoBuilding(UnitTypeId.GATEWAY, 10_000),
            ChronoBuilding(UnitTypeId.ROBOTICSFACILITY, 10_000),
            ChronoBuilding(UnitTypeId.STARGATE, 10_000),
            MorphWarpGates(),
            *_worker_economy_tools(),
        ]
    if race == Race.Zerg:
        return [
            PlanCancelBuilding(),
            OverlordScout(),
            InjectLarva(),
            SpreadCreep(),
            *_worker_economy_tools(),
        ]
    raise ValueError("Universal tactical tools require a concrete race, got {!r}".format(race))
