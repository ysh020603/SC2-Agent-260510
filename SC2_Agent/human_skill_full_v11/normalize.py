from __future__ import annotations

import re


ZERG_COMBAT = {
    "BANELING", "BROODLORD", "CORRUPTOR", "HYDRALISK", "INFESTOR", "LURKERMP",
    "MUTALISK", "QUEEN", "RAVAGER", "ROACH", "SWARMHOSTMP", "ULTRALISK", "VIPER", "ZERGLING",
}
TERRAN_COMBAT = {
    "BANSHEE", "BATTLECRUISER", "CYCLONE", "GHOST", "HELLION", "LIBERATOR", "MARAUDER",
    "MARINE", "MEDIVAC", "RAVEN", "REAPER", "SIEGETANK", "THOR", "VIKINGFIGHTER", "WIDOWMINE",
}


def _state(obs_text: str) -> dict[str, int]:
    resource = re.search(r"\[Economy\]\s*([0-9]+) minerals,\s*([0-9]+) vespene", obs_text, re.I)
    supply = re.search(
        r"Supply:\s*([0-9]+)\s*/\s*([0-9]+)\s*\(workers\s*([0-9]+)\s*/\s*([0-9]+).*?army\s*([0-9]+)",
        obs_text,
        re.I,
    )
    if not resource or not supply:
        return {}
    return {"bank": int(resource.group(1)) + int(resource.group(2)), "used": int(supply.group(1)),
            "cap": int(supply.group(2)), "workers": int(supply.group(3)),
            "ideal": int(supply.group(4)), "army": int(supply.group(5))}


def _own_entities(obs_text: str) -> set[str]:
    own = obs_text.split("[Enemy Intelligence]", 1)[0]
    return {name.upper() for name in re.findall(r"\b[0-9]+\s+([A-Z][A-Z0-9_]*)\b", own)}


def normalize_early_queue(*, race: str, obs_text: str, ordered_names: list[str], game_time_seconds: float,
                          zerg_combat_target: int = 10, zerg_until: float = 300,
                          zerg_add_production: bool = False) -> list[str]:
    state = _state(obs_text)
    if not state:
        return list(ordered_names)
    names = list(ordered_names)
    entities = _own_entities(obs_text)
    free_supply = state["cap"] - state["used"]

    if race.lower() == "zerg" and 75 <= game_time_seconds <= zerg_until and state["army"] < max(12, zerg_combat_target):
        allowed_drones = 2 if state["workers"] < state["ideal"] else 0
        drones = 0
        overlords = 0
        result: list[str] = []
        for name in names:
            upper = name.upper()
            if upper == "DRONE":
                if drones >= allowed_drones:
                    continue
                drones += 1
            if upper == "OVERLORD":
                if free_supply >= 16 or overlords >= 1:
                    continue
                overlords += 1
            result.append(name)
        pool_available = "SPAWNINGPOOL" in entities or any(name.upper() == "SPAWNINGPOOL" for name in result)
        if not pool_available:
            result.insert(0, "SpawningPool")
        combat = sum(name.upper() in ZERG_COMBAT for name in result)
        supply_needed = max(0, zerg_combat_target - combat)
        if free_supply < supply_needed and not any(name.upper() == "OVERLORD" for name in result):
            pool_position = 1 if result and result[0].upper() == "SPAWNINGPOOL" else 0
            result.insert(pool_position, "Overlord")
        result.extend(["Zergling"] * max(0, zerg_combat_target - combat))
        if zerg_add_production and state["bank"] >= 800:
            # After an immediate fighting wave, turn the persistent bank into
            # larva throughput and Queens instead of merely demanding more units.
            insertion = min(len(result), 12)
            result[insertion:insertion] = ["Queen", "Queen", "Queen", "Hatchery", "Hatchery"]
        return result[:30]

    if race.lower() == "terran" and 120 <= game_time_seconds <= 360 and state["army"] < 15 and state["bank"] >= 600:
        scvs = 0
        depots = 0
        result = []
        for name in names:
            upper = name.upper()
            if upper == "SCV":
                if scvs >= 2:
                    continue
                scvs += 1
            if upper == "SUPPLYDEPOT":
                if free_supply >= 16 or depots >= 1:
                    continue
                depots += 1
            result.append(name)
        live_production = sum(name in entities for name in ("BARRACKS", "FACTORY", "STARPORT"))
        ordered_production = sum(name.upper() in {"BARRACKS", "FACTORY", "STARPORT"} for name in result)
        additions: list[str] = []
        if live_production + ordered_production < 2:
            if "SUPPLYDEPOT" not in entities and not any(name.upper() == "SUPPLYDEPOT" for name in result):
                additions.append("SupplyDepot")
            additions.extend(["Barracks"] * (2 - live_production - ordered_production))
        result = additions + result
        combat = sum(name.upper() in TERRAN_COMBAT for name in result)
        if free_supply < max(0, 10 - combat) and not any(name.upper() == "SUPPLYDEPOT" for name in result):
            result.insert(0, "SupplyDepot")
        result.extend(["Marine"] * max(0, 10 - combat))
        return result[:30]
    return names
