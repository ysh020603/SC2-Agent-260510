"""Persistent universal tactical plan shared by all macro methods."""

from __future__ import annotations

from sc2.data import Race

from sharpy.plans import BuildOrder, SequentialList
from sharpy.plans.tactics import PlanFinishEnemy, PlanZoneDefense, PlanZoneGather
from sharpy.plans.tactics.terran import PlanZoneGatherTerran

from .adaptive_zone_attack import AdaptiveZoneAttack
from .battle_snapshot import BattleSnapshotBuilder
from .config import DEFAULT_CONFIG, UniversalTacticalConfig
from .controller import UniversalTacticalController
from .logging import TacticalTraceLogger
from .race_utilities import create_race_utility_tools


UNIVERSAL_TACTICAL_PROFILE = """\
Combat movement and attack timing are controlled by a shared state-driven tactical controller.

The tactical controller considers:
- live army advantage
- predicted enemy power
- army cohesion
- air/ground coverage
- local defense requirements
- supply pressure

The macro decision model does not directly choose unit movement or attack timing.
All skills and ablations use the same tactical configuration and existing Sharpy unit micro.
"""


def create_universal_tactical_plan(
    race: Race,
    *,
    config: UniversalTacticalConfig = DEFAULT_CONFIG,
    trace_directory: str = "",
    trace_skill_id=None,
) -> BuildOrder:
    """Create once per bot; its attack/controller instances remain persistent."""
    controller = UniversalTacticalController(config)
    builder = BattleSnapshotBuilder(config)
    trace = TacticalTraceLogger(trace_directory, trace_skill_id, config)
    gather = PlanZoneGatherTerran() if race == Race.Terran else PlanZoneGather()
    orders = [
        *create_race_utility_tools(race),
        PlanZoneDefense(),
        gather,
        AdaptiveZoneAttack(controller, builder, trace, config),
        PlanFinishEnemy(),
    ]
    return BuildOrder(SequentialList(orders))
