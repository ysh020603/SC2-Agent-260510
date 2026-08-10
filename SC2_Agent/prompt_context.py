"""Structured context shared by the macro decision prompt and strategy tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class StrategyAutomationProfile:
    """Human-readable contract for resource-free, script-owned behavior."""

    race: str
    strategy: str
    attack_threshold: int
    attack_gate: str
    defense: str
    rally: str
    scouting: str
    race_utilities: tuple[str, ...]
    special_behaviors: tuple[str, ...] = ()

    def render(self) -> str:
        utilities = "\n".join(f"* {item}" for item in self.race_utilities)
        special = "\n".join(f"* {item}" for item in self.special_behaviors)
        if not special:
            special = "* No additional strategy-specific tactical automation."
        return (
            f"Strategy: {self.strategy}\n"
            f"Attack trigger: the automated attack planner may launch when its "
            f"combat-power threshold reaches {self.attack_threshold}. "
            f"{self.attack_gate}\n"
            f"Defense: {self.defense}\n"
            f"Rally/gather: {self.rally}\n"
            f"Scouting: {self.scouting}\n"
            "Race utilities:\n"
            f"{utilities}\n"
            "Special behaviors:\n"
            f"{special}\n"
            "These behaviors are script-owned. Do not emit macro tasks merely "
            "to command, time, or position them."
        )


def terran_automation_profile(
    *,
    strategy: str,
    attack_threshold: int,
    attack_gate: str = "There is no additional composition or time gate.",
    special_behaviors: Iterable[str] = (),
) -> StrategyAutomationProfile:
    return StrategyAutomationProfile(
        race="terran",
        strategy=strategy,
        attack_threshold=attack_threshold,
        attack_gate=attack_gate,
        defense=(
            "PlanZoneDefense reacts to threats near owned zones; bunker manning "
            "and unfinished-building continuation are also automatic."
        ),
        rally=(
            "The army gathers at a safe Terran zone between attacks; the attack "
            "planner selects targets and controls the combat movement."
        ),
        scouting=(
            "A worker scouts after the first SupplyDepot exists, and ScanEnemy "
            "starts after 5:00 when orbital energy permits."
        ),
        race_utilities=(
            "Lower completed depots when appropriate.",
            "Call down MULEs automatically (50 energy before 5:00, conservative "
            "100-energy reserve afterward).",
            "Cancel doomed construction, distribute workers, speed-mine, and "
            "clear a blocked opening base automatically.",
            "PlanFinishEnemy searches for and destroys remaining enemy assets "
            "after normal targets disappear.",
        ),
        special_behaviors=tuple(special_behaviors),
    )


def protoss_automation_profile(
    *,
    strategy: str,
    attack_threshold: int,
    attack_gate: str = "There is no additional composition or time gate.",
    special_behaviors: Iterable[str] = (),
) -> StrategyAutomationProfile:
    return StrategyAutomationProfile(
        race="protoss",
        strategy=strategy,
        attack_threshold=attack_threshold,
        attack_gate=attack_gate,
        defense=(
            "PlanZoneDefense automatically reacts to threats near owned zones."
        ),
        rally=(
            "The army gathers at a safe owned zone between attacks; the attack "
            "planner selects targets, paths, and combat movement."
        ),
        scouting="A Probe scouting routine is automatic from the opening.",
        race_utilities=(
            "Chrono Boost is automatically assigned to active technology and "
            "key Nexus/Gateway/RoboticsFacility/Stargate production.",
            "Ready Gateways are automatically morphed to WarpGates after the "
            "research is available.",
            "Cancel doomed structures, distribute workers, speed-mine, and "
            "finish remaining enemy assets automatically.",
        ),
        special_behaviors=tuple(special_behaviors),
    )


def zerg_automation_profile(
    *,
    strategy: str,
    attack_threshold: int,
    attack_gate: str = "There is no additional composition or time gate.",
    spread_creep: bool = True,
    special_behaviors: Iterable[str] = (),
) -> StrategyAutomationProfile:
    creep = (
        "Queens spread creep automatically when tumors and energy are available."
        if spread_creep
        else "Automatic creep spreading is disabled for this early all-in."
    )
    return StrategyAutomationProfile(
        race="zerg",
        strategy=strategy,
        attack_threshold=attack_threshold,
        attack_gate=attack_gate,
        defense=(
            "PlanZoneDefense automatically reacts to threats near owned zones."
        ),
        rally=(
            "The army gathers at a safe owned zone between attacks; the attack "
            "planner selects targets, paths, and combat movement."
        ),
        scouting="Overlord scouting is automatic.",
        race_utilities=(
            "Queens inject Larva automatically when they have energy.",
            creep,
            "Cancel doomed structures, distribute workers, speed-mine, and "
            "finish remaining enemy assets automatically.",
        ),
        special_behaviors=tuple(special_behaviors),
    )


OBSERVATION_FIELD_GUIDE = """\
* Time: current in-game clock for this decision, not wall-clock/API time.
* Resources: current minerals and vespene. Income is the estimated amount per
  in-game minute; it is a rate, not resources already available.
* Supply used/cap/free: used army+worker supply, current maximum, and
  cap-minus-used. Supply providers under construction do not count in cap yet.
* Workers current/ideal: living workers versus the displayed saturation slots
  of ready town halls and gas structures. It is an economic saturation guide,
  not a mandatory final worker target.
* Army supply: supply currently occupied by combat units; it is not the same
  as unit count or the combat analyzer's power value.
* Completed: ready own units/structures. Under Construction includes unfinished
  foundations, morphs, and units already in production.
* Workers En Route: a worker has received a build order but the structure
  foundation is not visible yet. Treat it as committed work and do not duplicate it.
* Active Queues: production, morph, or research orders already accepted by the
  SC2 engine. Do not request the same work solely because it is absent from Completed.
* Enemy Intelligence: remembered/historically observed enemy counts, not
  omniscient live vision. Stale units may already be dead or elsewhere.
* Map Control: owned/enemy/contested zones inferred by the zone manager.
* Army/Income Advantage: relative comparison estimates. Positive favors us;
  negative favors the enemy.
* Power: an abstract combat-analyzer strength estimate used by automated
  attack/defense logic. It is not supply, unit count, or a guaranteed outcome.
* Losses: observed cumulative resource-value losses.
* Research & Technology lists completed upgrades. Research currently running
  appears in Active Queues instead.
* Threat Flags: detector/build-analyzer warnings. They are evidence to react to,
  not certainty about unseen enemy plans."""


def decision_lifecycle_context(*, decision_interval_seconds: float) -> str:
    interval = f"{decision_interval_seconds:g}"
    return f"""\
* A decision is triggered once at game start.
* It is triggered again every configured {interval} in-game seconds.
* It may also trigger early when a previously non-empty macro queue becomes
  drained, but never sooner than 5 in-game seconds after the previous decision.
* Each decision receives a fresh observation and only canonical names from the
  previous queue that have not yet been committed to the SC2 engine.
* The previous explanation, full prompt, and completed queue history are not
  carried into the next decision. Infer continuity from the fresh observation,
  strategy objective, and uncommitted names.
* An accepted response atomically replaces all uncommitted tasks. Work already
  accepted by the SC2 engine remains untouched.
* Invalid JSON, or a non-empty answer with no executable mapped tasks, is
  rejected and the old uncommitted queue remains active."""


__all__ = [
    "OBSERVATION_FIELD_GUIDE",
    "StrategyAutomationProfile",
    "decision_lifecycle_context",
    "protoss_automation_profile",
    "terran_automation_profile",
    "zerg_automation_profile",
]
