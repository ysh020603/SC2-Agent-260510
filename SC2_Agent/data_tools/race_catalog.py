"""Race-aware canonical macro catalogs and entity-to-action resolution.

The graph database contains far more entities than a macro planner should see:
temporary modes, burrowed forms, summoned units, placement abilities, and
legacy units all coexist with normal ladder units.  This module exposes an
explicit, reviewed macro surface for each playable race while still deriving
the concrete abilities, executors, prerequisites, and upgrades from the
database.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable

from .sc2_data_common import (
    action_result_names,
    build_ability_index,
    build_entity_indexes,
    build_executor_index,
    load_database,
    target_kind_and_result,
)


@dataclass(frozen=True)
class RaceMechanics:
    race: str
    overview: str
    strengths: tuple[str, ...]
    tradeoffs: tuple[str, ...]
    decision_implications: tuple[str, ...]
    worker: str
    supply_provider: str
    townhall: str
    gas_structure: str
    notes: tuple[str, ...]


@dataclass(frozen=True)
class ActionCandidate:
    ability_name: str
    target_kind: str
    target_result: str
    executors: tuple[str, ...]
    execution_mode: str
    output_count: int = 1


RACE_MECHANICS: dict[str, RaceMechanics] = {
    "terran": RaceMechanics(
        race="Terran",
        overview=(
            "Terran uses conventional structure construction, separate unit "
            "production buildings, and building-specific TechLab/Reactor add-ons. "
            "Its army rewards combined arms, ranged concentration, and flexible "
            "production switches."
        ),
        strengths=(
            "Durable ranged armies and strong defensive structures.",
            "Reactors increase unit throughput while TechLabs unlock advanced units and research.",
            "Orbital Command energy provides MULE economy and Scanner Sweep information.",
        ),
        tradeoffs=(
            "SCVs remain occupied while constructing and can be exposed.",
            "Add-ons need clear space and bind technology/throughput to a specific production building.",
            "Many strong compositions need several complementary production lines and upgrades.",
        ),
        decision_implications=(
            "Plan concrete Barracks/Factory/Starport add-ons before dependent units or research.",
            "Add enough production capacity to spend mineral banks; do not rely on automated macro spending.",
            "Leave MULEs, scans, depot lowering, repair-adjacent tactics, positioning, and combat control to scripts.",
        ),
        worker="SCV",
        supply_provider="SupplyDepot",
        townhall="CommandCenter",
        gas_structure="Refinery",
        notes=(
            "SCVs remain occupied while constructing Terran structures.",
            "SupplyDepot is the normal supply provider.",
            "Barracks, Factory, and Starport add-ons require clear space on the building's right.",
            "Use BarracksTechLab/BarracksReactor, FactoryTechLab/FactoryReactor, "
            "or StarportTechLab/StarportReactor; never use bare TechLab or Reactor.",
            "The canonical upgrade name for the in-game Combat Shield is ShieldWall.",
        ),
    ),
    "protoss": RaceMechanics(
        race="Protoss",
        overview=(
            "Protoss invests in expensive, high-impact units and technology. "
            "Most structures depend on Pylon power, Gateway production can shift "
            "to WarpGate, and Chrono Boost accelerates selected production or research."
        ),
        strengths=(
            "High unit quality and strong technology power spikes.",
            "WarpGate enables flexible reinforcement once researched and morphed.",
            "Chrono Boost can accelerate important production and upgrades.",
        ),
        tradeoffs=(
            "Units and technology are expensive, so losses and premature tech branches are costly.",
            "Most structures stop functioning without nearby Pylon power.",
            "Gateway and WarpGate share the same strategic production role rather than being independent capacity.",
        ),
        decision_implications=(
            "Build a Pylon before structures that need power and protect production power coverage.",
            "Request Gateway units by canonical unit name; the runtime chooses Gateway training or WarpGate warp-in.",
            "WarpGate is not a macro output: request Gateway for added capacity "
            "and WarpGateResearch for the upgrade; scripts perform the morph.",
            "Leave Chrono Boost assignment, WarpGate morphing, warp-in positions, and combat control to scripts.",
        ),
        worker="Probe",
        supply_provider="Pylon",
        townhall="Nexus",
        gas_structure="Assimilator",
        notes=(
            "Most Protoss structures require power from a completed Pylon.",
            "Gateway units may be trained from a Gateway or warped in from a ready WarpGate.",
            "The runtime chooses a powered warp-in position; do not emit positions.",
            "Preserve the exact spelling and capitalization of every canonical name.",
        ),
    ),
    "zerg": RaceMechanics(
        race="Zerg",
        overview=(
            "Zerg shares Larva between workers and most army units, consumes "
            "Drones to morph structures, and uses Hatchery tech morphs plus creep "
            "to expand its production and map presence."
        ),
        strengths=(
            "Larva allows rapid production switches and large reinforcement bursts.",
            "Queens provide Larva injection and creep support without consuming Larva.",
            "Mobile armies and morph paths can adapt an existing composition.",
        ),
        tradeoffs=(
            "Workers and army directly compete for Larva.",
            "Every normal structure costs a Drone in addition to minerals.",
            "Most structures require creep and advanced units depend on morph/tech chains.",
        ),
        decision_implications=(
            "Balance Drone growth against immediate army Larva; repeated unit names consume repeated Larva commands.",
            "Account for the Drone lost to each structure and rebuild workers when economically appropriate.",
            "Leave injections, creep spread, Overlord scouting, positions, and combat control to scripts.",
        ),
        worker="Drone",
        supply_provider="Overlord",
        townhall="Hatchery",
        gas_structure="Extractor",
        notes=(
            "Most Zerg units consume Larva; Larva is a renewable production resource.",
            "A Drone is consumed when it morphs into a Zerg structure.",
            "One Zergling queue entry is one Larva production command and produces two Zerglings.",
            "Most Zerg structures require creep; Hatchery and Extractor are exceptions.",
            "Use the singular canonical name Extractor and repeat it for multiple gas structures.",
        ),
    ),
}


_RACE_ENTITY_ALIASES: dict[str, dict[str, str]] = {
    "terran": {
        "combatshield": "ShieldWall",
        "combatshields": "ShieldWall",
        "refineries": "Refinery",
    },
    "protoss": {
        "assimilators": "Assimilator",
    },
    "zerg": {
        "extractors": "Extractor",
    },
}


# Reviewed macro outcomes.  Mode-only, summoned, spell-created, and positional
# tactical entities intentionally stay out of the LLM-facing surface.
_PROTOSS_UNITS = (
    "Probe",
    "Pylon",
    "Assimilator",
    "Nexus",
    "Gateway",
    "CyberneticsCore",
    "Forge",
    "PhotonCannon",
    "ShieldBattery",
    "TwilightCouncil",
    "TemplarArchive",
    "DarkShrine",
    "RoboticsFacility",
    "RoboticsBay",
    "Stargate",
    "FleetBeacon",
    "Zealot",
    "Stalker",
    "Adept",
    "Sentry",
    "HighTemplar",
    "DarkTemplar",
    "Archon",
    "Observer",
    "WarpPrism",
    "Immortal",
    "Colossus",
    "Disruptor",
    "Phoenix",
    "VoidRay",
    "Oracle",
    "Carrier",
    "Tempest",
    "Mothership",
)

_ZERG_UNITS = (
    "Drone",
    "Overlord",
    "Extractor",
    "Hatchery",
    "SpawningPool",
    "EvolutionChamber",
    "RoachWarren",
    "BanelingNest",
    "SpineCrawler",
    "SporeCrawler",
    "Lair",
    "HydraliskDen",
    "InfestationPit",
    "Spire",
    "NydusNetwork",
    "Hive",
    "GreaterSpire",
    "LurkerDenMP",
    "UltraliskCavern",
    "Queen",
    "Zergling",
    "Baneling",
    "Roach",
    "Ravager",
    "Hydralisk",
    "LurkerMP",
    "Mutalisk",
    "Corruptor",
    "BroodLord",
    "Infestor",
    "SwarmHostMP",
    "Ultralisk",
    "Viper",
    "Overseer",
    "OverlordTransport",
)


def normalize_race(race: str) -> str:
    value = str(race or "").split(".")[-1].strip().lower()
    if value not in RACE_MECHANICS:
        raise ValueError(f"Unsupported playable race: {race!r}")
    return value


def race_mechanics(race: str) -> RaceMechanics:
    return RACE_MECHANICS[normalize_race(race)]


def _is_normal_production_candidate(
    *,
    race: str,
    entity_name: str,
    ability_name: str,
    target_kind: str,
    executors: Iterable[str],
) -> bool:
    executors = set(executors)
    if race == "terran":
        if ability_name.startswith(("BUILD_TECHLAB_", "BUILD_REACTOR_")):
            return True
        if target_kind in {"Build", "BuildOnUnit", "BuildInstant"}:
            return "SCV" in executors
        if target_kind in {"Train", "Research"}:
            return True
        return entity_name in {"OrbitalCommand", "PlanetaryFortress"}

    if race == "protoss":
        if entity_name == "Archon":
            return ability_name == "MORPH_ARCHON"
        if target_kind in {"Build", "BuildOnUnit"}:
            return "Probe" in executors
        if target_kind in {"Train", "TrainPlace", "Research"}:
            return True
        return False

    # Zerg: explicitly distinguish production morphs from burrow/mode morphs.
    if target_kind in {"Build", "BuildOnUnit"}:
        return "Drone" in executors or ability_name == "TRAINQUEEN_QUEEN"
    if target_kind == "Research":
        return True
    if ability_name.startswith("LARVATRAIN_") or ability_name == "TRAIN_SWARMHOST":
        return True
    if ability_name in {
        "MORPHTOBANELING_BANELING",
        "MORPHTORAVAGER_RAVAGER",
        "MORPH_LURKER",
        "MORPHTOBROODLORD_BROODLORD",
        "MORPH_OVERSEER",
        "MORPH_OVERLORDTRANSPORT",
        "UPGRADETOLAIR_LAIR",
        "UPGRADETOHIVE_HIVE",
        "UPGRADETOGREATERSPIRE_GREATERSPIRE",
    }:
        return True
    return False


def _execution_mode(
    race: str,
    entity_name: str,
    ability_name: str,
    target_kind: str,
) -> str:
    if ability_name.startswith(("BUILD_TECHLAB_", "BUILD_REACTOR_")):
        return "addon"
    if entity_name in {"CommandCenter", "Nexus", "Hatchery"}:
        return "expand"
    if entity_name in {"Refinery", "Assimilator", "Extractor"}:
        return "gas"
    if ability_name == "MORPH_ARCHON":
        return "paired_morph"
    if target_kind == "TrainPlace":
        return "warp_in"
    if ability_name == "TRAINQUEEN_QUEEN":
        return "train"
    if target_kind == "Research":
        return "research"
    if target_kind in {"Build", "BuildOnUnit", "BuildInstant"}:
        return "worker_build"
    if target_kind == "Train":
        return "train"
    if target_kind in {"Morph", "MorphPlace"}:
        return "morph"
    return "unsupported"


def _candidate_rank(candidate: ActionCandidate) -> tuple[int, str]:
    order = {
        "expand": 0,
        "gas": 0,
        "worker_build": 0,
        "addon": 0,
        "train": 1,
        "research": 2,
        "morph": 3,
        "warp_in": 4,
        "paired_morph": 5,
    }
    return order.get(candidate.execution_mode, 99), candidate.ability_name


@lru_cache(maxsize=3)
def _catalog(race: str) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, tuple[ActionCandidate, ...]]]:
    race = normalize_race(race)
    mechanics = race_mechanics(race)
    data = load_database()
    units, upgrades = build_entity_indexes(data)
    abilities = build_ability_index(data)
    executors = build_executor_index(data, race=mechanics.race)

    if race == "terran":
        # Import lazily so existing Terran selection remains byte-for-byte
        # compatible while the shared catalog becomes the public API.
        from .terran_names import terran_unit_names, terran_upgrade_names

        allowed_units = set(terran_unit_names())
        allowed_upgrades = set(terran_upgrade_names())
    elif race == "protoss":
        allowed_units = set(_PROTOSS_UNITS)
        allowed_upgrades = set()
    else:
        allowed_units = set(_ZERG_UNITS)
        allowed_upgrades = set()

    candidate_map: dict[str, list[ActionCandidate]] = {}
    for ability_name, ability in abilities.items():
        action_executors = tuple(sorted(executors.get(ability_name, set())))
        if not action_executors:
            continue
        target_kind, target_result = target_kind_and_result(ability)
        target_kind = target_kind or ""
        for entity_name in action_result_names(ability):
            if entity_name not in units and entity_name not in upgrades:
                continue
            is_upgrade = entity_name in upgrades
            if is_upgrade and target_kind == "Research":
                if race != "terran":
                    allowed_upgrades.add(entity_name)
            allowed = entity_name in (allowed_upgrades if is_upgrade else allowed_units)
            if not allowed:
                continue
            if not _is_normal_production_candidate(
                race=race,
                entity_name=entity_name,
                ability_name=ability_name,
                target_kind=target_kind,
                executors=action_executors,
            ):
                continue
            mode = _execution_mode(race, entity_name, ability_name, target_kind)
            if mode == "unsupported":
                continue
            candidate_map.setdefault(entity_name, []).append(
                ActionCandidate(
                    ability_name=ability_name,
                    target_kind=target_kind,
                    # Some SC2 graph morphs use the placeholder ``NOTAUNIT`` in
                    # their target payload while the action_result relation has
                    # the real canonical outcome.
                    target_result=entity_name,
                    executors=action_executors,
                    execution_mode=mode,
                    output_count=2 if ability_name == "LARVATRAIN_ZERGLING" else 1,
                )
            )

    # Only expose entities that survived action-policy validation.
    unit_names = tuple(sorted(name for name in allowed_units if candidate_map.get(name)))
    upgrade_names = tuple(sorted(name for name in allowed_upgrades if candidate_map.get(name)))
    frozen_candidates = {
        name: tuple(sorted(rows, key=_candidate_rank))
        for name, rows in candidate_map.items()
        if name in set(unit_names) | set(upgrade_names)
    }
    return unit_names, upgrade_names, frozen_candidates


def race_unit_names(race: str) -> list[str]:
    return list(_catalog(normalize_race(race))[0])


def race_upgrade_names(race: str) -> list[str]:
    return list(_catalog(normalize_race(race))[1])


def _entity_alias_key(name: str) -> str:
    return "".join(character for character in str(name or "").lower() if character.isalnum())


def canonical_race_entity_name(race: str, name: str) -> str | None:
    """Resolve a model name to one unambiguous race-catalog entity.

    Exact canonical spelling wins.  Explicit SC2 vocabulary aliases are
    reviewed above.  A capitalization-only variation is accepted only when it
    identifies exactly one Unit/Upgrade catalog entry; known Unit/Upgrade name
    collisions therefore remain rejected instead of guessing.
    """

    race = normalize_race(race)
    units, upgrades, _candidates = _catalog(race)
    if name in units or name in upgrades:
        return name

    alias = _RACE_ENTITY_ALIASES.get(race, {}).get(_entity_alias_key(name))
    if alias is not None and (alias in units or alias in upgrades):
        return alias

    folded = str(name or "").casefold()
    matches = [
        canonical
        for group in (units, upgrades)
        for canonical in group
        if canonical.casefold() == folded
    ]
    return matches[0] if len(matches) == 1 else None


def is_known_race_entity(race: str, name: str) -> bool:
    return canonical_race_entity_name(race, name) is not None


def action_candidates_for_entity(race: str, name: str) -> list[ActionCandidate]:
    race = normalize_race(race)
    canonical_name = canonical_race_entity_name(race, name)
    if canonical_name is None:
        return []
    return list(_catalog(race)[2].get(canonical_name, ()))


def race_prompt_context(race: str) -> str:
    mechanics = race_mechanics(race)
    strengths = "\n".join(f"* {item}" for item in mechanics.strengths)
    tradeoffs = "\n".join(f"* {item}" for item in mechanics.tradeoffs)
    implications = "\n".join(
        f"* {item}" for item in mechanics.decision_implications
    )
    notes = "\n".join(f"* {note}" for note in mechanics.notes)
    return (
        f"Overview: {mechanics.overview}\n"
        f"Strengths:\n{strengths}\n"
        f"Tradeoffs:\n{tradeoffs}\n"
        f"Macro decision implications:\n{implications}\n"
        f"Worker: {mechanics.worker}\n"
        f"Supply provider: {mechanics.supply_provider}\n"
        f"Town hall: {mechanics.townhall}\n"
        f"Gas structure: {mechanics.gas_structure}\n"
        "Exact mechanics:\n"
        f"{notes}"
    )


__all__ = [
    "ActionCandidate",
    "RaceMechanics",
    "action_candidates_for_entity",
    "canonical_race_entity_name",
    "is_known_race_entity",
    "normalize_race",
    "race_mechanics",
    "race_prompt_context",
    "race_unit_names",
    "race_upgrade_names",
]
