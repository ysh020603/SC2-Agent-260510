from __future__ import annotations

import re

from SC2_Agent.data_tools import action_candidates_for_entity, check_action_prerequisites


ZERG_COMBAT = {
    "QUEEN", "ZERGLING", "BANELING", "ROACH", "RAVAGER", "HYDRALISK", "LURKERMP",
    "MUTALISK", "CORRUPTOR", "BROODLORD", "INFESTOR", "SWARMHOSTMP", "ULTRALISK", "VIPER",
}
TERRAN_COMBAT = {
    "MARINE", "MARAUDER", "REAPER", "GHOST", "HELLION", "WIDOWMINE", "SIEGETANK",
    "CYCLONE", "THOR", "VIKINGFIGHTER", "MEDIVAC", "LIBERATOR", "RAVEN", "BANSHEE",
    "BATTLECRUISER",
}


def _economy(obs_text: str) -> dict[str, int]:
    resource = re.search(r"\[Economy\]\s*([0-9]+) minerals,\s*([0-9]+) vespene", obs_text, re.I)
    supply = re.search(
        r"Supply:\s*([0-9]+)\s*/\s*([0-9]+)\s*\(workers\s*([0-9]+)\s*/\s*([0-9]+)\s*current/ideal,\s*army\s*([0-9]+)",
        obs_text,
        re.I,
    )
    if not resource or not supply:
        return {}
    return {
        "bank": int(resource.group(1)) + int(resource.group(2)),
        "used": int(supply.group(1)),
        "cap": int(supply.group(2)),
        "workers": int(supply.group(3)),
        "ideal": int(supply.group(4)),
        "army": int(supply.group(5)),
    }


def _entities_from_line(obs_text: str, label: str) -> list[str]:
    match = re.search(rf"^\s*{re.escape(label)}:\s*(.*?)\.\s*$", obs_text, re.I | re.M)
    if not match or match.group(1).strip().lower() == "none":
        return []
    return [name for _count, name in re.findall(r"(?:^|,\s*)([0-9]+)\s+([A-Z][A-Z0-9_]*)", match.group(1))]


def _entity_set(obs_text: str) -> set[str]:
    return {name.upper() for name in _entities_from_line(obs_text, "Completed") + _entities_from_line(obs_text, "Under Construction")}


def race_macro_error(*, race: str, obs_text: str, ordered_names: list[str], game_time_seconds: float) -> str:
    economy = _economy(obs_text)
    if not economy:
        return ""
    names = [name.upper() for name in ordered_names]
    entities = _entity_set(obs_text)
    free_supply = economy["cap"] - economy["used"]

    if race.lower() == "zerg":
        issues: list[str] = []
        pool_available = "SPAWNINGPOOL" in entities or "SPAWNINGPOOL" in names
        if game_time_seconds >= 75 and not pool_available:
            issues.append("put SpawningPool before dependent Queens/Zerglings")
        overlords = names.count("OVERLORD")
        # Only block clearly wasteful supply actions.  Routine mid/late-game
        # buffering is strategic and should stay under the LLM's control.
        supply_pathological = economy["army"] < 15 or free_supply >= 40
        if supply_pathological and free_supply >= 20 and overlords:
            issues.append(f"remove Overlord entries because free supply is already {free_supply}")
        elif overlords > 1:
            issues.append("keep at most one Overlord entry")
        if game_time_seconds >= 90 and economy["army"] < 8:
            drones = names.count("DRONE")
            allowed_drones = 0 if economy["workers"] >= economy["ideal"] else 2
            if drones > allowed_drones:
                issues.append(
                    f"keep at most {allowed_drones} Drone entries at workers {economy['workers']}/{economy['ideal']}"
                )
            combat = sum(name in ZERG_COMBAT for name in names)
            required = 8 if economy["bank"] >= 750 else 4
            if combat < required:
                issues.append(f"include at least {required} executable combat-unit entries after prerequisites")
        if issues:
            return (
                f"V8 Zerg executable repair (army {economy['army']}, bank {economy['bank']}): "
                + "; ".join(issues)
                + ". Return one complete replacement queue and spend freed Larva on immediate defense."
            )

    if race.lower() == "terran":
        issues = []
        depots = names.count("SUPPLYDEPOT")
        # Preserve normal production planning once a viable army exists; the
        # guard is for the observed low-army / massive-free-supply failures.
        supply_pathological = economy["army"] < 15 or free_supply >= 40
        if supply_pathological and free_supply >= 24 and depots:
            issues.append(f"remove SupplyDepot entries because free supply is already {free_supply}")
        elif depots > 1:
            issues.append("keep at most one SupplyDepot entry")
        if game_time_seconds >= 150 and economy["army"] < 15:
            scvs = names.count("SCV")
            if economy["workers"] >= economy["ideal"] + 3 and scvs > 1:
                issues.append(f"keep at most one SCV entry at workers {economy['workers']}/{economy['ideal']}")
            if economy["bank"] >= 750:
                live_production = sum(name in entities for name in ("BARRACKS", "FACTORY", "STARPORT"))
                ordered_production = sum(name in {"BARRACKS", "FACTORY", "STARPORT"} for name in names)
                if live_production + ordered_production < 2:
                    issues.append("put enough executable production before units to reach at least two sources")
                combat = sum(name in TERRAN_COMBAT for name in names)
                if combat < 8:
                    issues.append("include at least eight executable combat-unit entries after production/prerequisites")
        if issues:
            return (
                f"V8 Terran executable repair (army {economy['army']}, bank {economy['bank']}): "
                + "; ".join(issues)
                + ". Return one complete replacement queue that converts resources into fighting capacity."
            )
    return ""


def prerequisite_error(*, race: str, obs_text: str, ordered_names: list[str]) -> str:
    if race.lower() == "protoss":
        return ""
    entities = _entities_from_line(obs_text, "Completed") + _entities_from_line(obs_text, "Under Construction")
    abilities: list[str] = []
    mapped_names: list[str] = []
    for name in ordered_names:
        candidates = list(action_candidates_for_entity(race, name))
        if not candidates:
            continue
        abilities.append(candidates[0].ability_name)
        mapped_names.append(name)
    if not abilities:
        return ""
    report = check_action_prerequisites(entities, abilities)
    worker_executors = {"SCV", "PROBE", "DRONE", "LARVA"}
    for item, entity_name in zip(report.get("ordered_reports", []), mapped_names):
        missing = item.get("missing_requirements") or []
        if missing:
            requirement = missing[0]
            accepted = requirement.get("accepted_alternatives") or [requirement.get("entity_name")]
            accepted_upper = {str(value).upper() for value in accepted if value}
            if accepted_upper and accepted_upper.issubset(worker_executors):
                continue
            needed = "/".join(str(value) for value in accepted if value)
            later = requirement.get("provided_later_by") or []
            order_note = "; the provider is currently later in the queue" if later else ""
            return (
                f"V8 prerequisite repair: {entity_name} is not executable because {needed} is missing{order_note}. "
                "Place the complete missing tech chain before the dependent action, or replace it with a unit executable now."
            )
        missing_executors = item.get("missing_executors") or []
        if missing_executors:
            accepted = set(missing_executors[0].get("accepted_executors") or [])
            accepted_upper = {value.upper() for value in accepted}
            if accepted and not accepted_upper.intersection(worker_executors):
                needed = "/".join(sorted(accepted))
                return (
                    f"V8 prerequisite repair: {entity_name} has no completed or earlier ordered executor ({needed}). "
                    "Put the producer before the dependent action or select an executable alternative."
                )
    return ""
