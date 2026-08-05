"""Deterministic planning helpers for the V2 macro decision agent."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

from .query.data_store import DEFAULT_DATABASE_PATH, get_dataset_store


GAME_LOOPS_PER_SECOND = 22.4
SUPPLY_PROVIDER_BONUS = 8.0
SUPPLY_PROVIDERS = {"SupplyDepot", "Pylon", "Overlord"}
WORKER_NAMES = {"SCV", "Probe", "Drone"}
GAS_STRUCTURES = {"terran": "Refinery", "protoss": "Assimilator", "zerg": "Extractor"}
TOWNHALL_KEYS = {
    "commandcenter", "orbitalcommand", "planetaryfortress",
    "nexus", "hatchery", "lair", "hive",
}
MAX_LEDGER_ENTRIES = 24

# V2 harness primitives.  These are deliberately small, race-native fallback
# sets rather than a second strategy implementation: the MainAgent still owns
# composition, while the harness guarantees that a high bank can become
# executable production instead of an invalid or gas-locked queue.
RACE_EXECUTION_PROFILES = {
    "terran": {
        "primary_production": "Barracks",
        "production_assets": {"Barracks", "Factory", "Starport"},
        "mineral_sink": ("Marine",),
        "anti_air": ("Marine", "VikingFighter"),
        "anti_ground": ("Marine", "Hellion"),
        "commands_per_producer_per_minute": 2.5,
    },
    "protoss": {
        "primary_production": "Gateway",
        "production_assets": {"Gateway", "WarpGate", "RoboticsFacility", "Stargate"},
        "mineral_sink": ("Zealot",),
        "anti_air": ("Stalker",),
        "anti_ground": ("Zealot", "Stalker"),
        "commands_per_producer_per_minute": 2.2,
    },
    "zerg": {
        "primary_production": "Hatchery",
        "production_assets": {"Hatchery", "Lair", "Hive"},
        "mineral_sink": ("Zergling", "Queen"),
        "anti_air": ("Hydralisk", "Queen"),
        "anti_ground": ("Zergling", "Roach"),
        "commands_per_producer_per_minute": 3.0,
    },
}


def _number(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else 0.0


def _response_shortfall(required: float, actual: float) -> float:
    # Combat scores are derived from dataset supply and can differ by tiny
    # morph/paired-unit rounding amounts.  Less than half a supply is not a
    # meaningful missing response and must not invalidate a whole decision.
    value = max(0.0, required - actual)
    return 0.0 if value < 0.5 else round(value, 2)


def normalize_question(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value).lower()).split())


def ledger_key(question: str, query_type: str = "", targets: list[str] | None = None) -> str:
    normalized_targets = sorted(_asset_key(item) for item in (targets or []) if str(item).strip())
    if query_type and normalized_targets:
        return f"{_asset_key(query_type)}|{'|'.join(normalized_targets)}"
    return normalize_question(question)


def _count_assets(rows: dict[str, Any], names: set[str]) -> float:
    wanted = {_asset_key(name) for name in names}
    return sum(
        _number(count)
        for name, count in rows.items()
        if _asset_key(name) in wanted
    )


def _build_task_decomposition(
    *,
    race: str,
    horizon: float,
    minerals: float,
    gas: float,
    mineral_income: float,
    gas_income: float,
    workers: float,
    ideal_workers: float,
    townhall_count: float,
    completed: dict[str, Any],
    combat: dict[str, Any],
    layer_profile: dict[str, Any],
    bank_rising: bool,
) -> dict[str, Any]:
    """Turn one dense observation into ordered macro tasks for the harness."""

    profile = RACE_EXECUTION_PROFILES.get(race, {})
    production_assets = set(profile.get("production_assets") or set())
    ready_producers = _count_assets(completed, production_assets)
    our_power = _number(combat.get("our_army_power"))
    enemy_power = _number(combat.get("enemy_army_power"))
    ratio = our_power / enemy_power if enemy_power else None
    advantage_text = " ".join(str(combat.get(key) or "") for key in (
        "army_advantage", "advantage_predicted"
    )).lower()
    recovery = townhall_count <= 0 or workers <= 6
    emergency = bool(
        "overwhelmingdisadvantage" in advantage_text
        or "cleardisadvantage" in advantage_text
        or (enemy_power >= 2 and our_power <= 0)
        or (enemy_power >= 4 and ratio is not None and ratio < 0.65)
    )
    mineral_overflow = minerals >= 1000 and (bank_rising or minerals >= 2000)
    gas_overflow = gas >= 800 and minerals >= 400
    resource_overflow = mineral_overflow or gas_overflow
    layer_gap = bool(layer_profile.get("air_attack_gap") or layer_profile.get("ground_attack_gap"))

    spend_pressure_per_minute = (
        mineral_income
        + gas_income * 0.75
        + max(0.0, minerals - 600.0) * 60.0 / max(30.0, horizon)
        + max(0.0, gas - 500.0) * 30.0 / max(30.0, horizon)
    )
    supported_per_producer = 300.0
    desired_producers = min(8, max(1, int(math.ceil(spend_pressure_per_minute / supported_per_producer))))
    production_gap = resource_overflow and ready_producers < desired_producers
    production_additions = min(2, max(0, desired_producers - int(ready_producers)))
    command_capacity = max(
        2,
        int(math.ceil(
            ready_producers
            * _number(profile.get("commands_per_producer_per_minute"))
            * horizon / 60.0
        )),
    )
    if production_additions:
        # A producer added this horizon contributes only partial near-term
        # throughput; do not pretend a new building is immediately saturated.
        command_capacity += production_additions
    command_capacity = min(16, command_capacity)

    tasks: list[dict[str, Any]] = []
    if recovery:
        tasks.append({"task": "base_and_worker_recovery", "priority": 100, "budget_share": 0.25})
    if emergency:
        tasks.append({"task": "immediate_survival_force", "priority": 95, "budget_share": 0.70})
    if layer_gap:
        tasks.append({"task": "verified_attack_layer_response", "priority": 90, "budget_share": 0.55})
    if resource_overflow:
        tasks.append({"task": "convert_bank_to_mobile_strength", "priority": 80, "budget_share": 0.55})
    if production_gap:
        tasks.append({"task": "expand_executable_production", "priority": 75, "budget_share": 0.25})
    if not emergency and not recovery:
        tasks.append({"task": "strategy_technology_and_upgrades", "priority": 45, "budget_share": 0.20})
    if workers < ideal_workers and not emergency:
        tasks.append({"task": "worker_saturation", "priority": 40, "budget_share": 0.20})
    if not tasks:
        tasks.append({"task": "routine_strategy_continuation", "priority": 30, "budget_share": 1.0})
    tasks.sort(key=lambda item: int(item["priority"]), reverse=True)

    return {
        "operational_mode": (
            "recovery" if recovery else "survival" if emergency else
            "counter_response" if layer_gap else "bank_conversion" if resource_overflow else "normal"
        ),
        "ordered_tasks": tasks,
        "hard_priority_rule": (
            "survival/counter units before workers, expansions, luxury technology, or upgrades"
            if emergency or layer_gap else
            "production and mobile units before extra economy while the bank is rising"
            if resource_overflow else
            "follow the strategy while preserving supply and saturation"
        ),
        "recovery_mode": recovery,
        "combat_emergency": emergency,
        "resource_overflow": resource_overflow,
        "mineral_overflow": mineral_overflow,
        "gas_overflow": gas_overflow,
        "attack_layer_gap": layer_gap,
        "production_capacity": {
            "ready_producer_equivalents": round(ready_producers, 2),
            "estimated_mobile_commands_this_horizon": command_capacity,
            "desired_producer_equivalents": desired_producers,
            "capacity_gap": production_gap,
            "recommended_structure": profile.get("primary_production") if production_gap else None,
            "recommended_additions": production_additions,
        },
        "fallback_units": {
            "mineral_sink": list(profile.get("mineral_sink") or ()),
            "anti_air": list(profile.get("anti_air") or ()),
            "anti_ground": list(profile.get("anti_ground") or ()),
        },
    }


def build_planning_snapshot(
    observation: dict[str, Any] | None,
    *,
    horizon_seconds: float,
    previous: dict[str, Any] | None = None,
    race: str = "",
    data_path: str | Path = DEFAULT_DATABASE_PATH,
) -> dict[str, Any]:
    observation = observation or {}
    economy = observation.get("economy") if isinstance(observation.get("economy"), dict) else {}
    own_forces = observation.get("own_forces") if isinstance(observation.get("own_forces"), dict) else {}
    enemy = observation.get("enemy") if isinstance(observation.get("enemy"), dict) else {}
    combat = observation.get("combat") if isinstance(observation.get("combat"), dict) else {}
    memory_flags = observation.get("memory_flags") if isinstance(observation.get("memory_flags"), dict) else {}
    horizon = max(15.0, min(float(horizon_seconds or 60.0), 90.0))
    minerals = _number(economy.get("minerals"))
    gas = _number(economy.get("vespene"))
    mineral_income = _number(economy.get("minerals_per_min"))
    gas_income = _number(economy.get("vespene_per_min"))
    supply_used = _number(economy.get("supply_used"))
    supply_cap = _number(economy.get("supply_cap"))
    supply_free = _number(economy.get("supply_left")) or max(0.0, supply_cap - supply_used)
    workers = _number(economy.get("supply_workers"))
    ideal_workers = _number(economy.get("ideal_worker_count"))
    previous = previous or {}
    previous_minerals = previous.get("minerals")
    previous_gas = previous.get("gas")
    previous_time = previous.get("game_time_seconds")
    game_time = _number(observation.get("time"))
    elapsed = max(0.0, game_time - _number(previous_time)) if previous_time is not None else 0.0
    bank_trend = {
        "sample_seconds": round(elapsed, 2),
        "minerals_delta": round(minerals - _number(previous_minerals), 2) if previous_minerals is not None else None,
        "gas_delta": round(gas - _number(previous_gas), 2) if previous_gas is not None else None,
    }
    layer_profile = _combat_layer_profile(observation, data_path=data_path)
    race_key = str(race or "").lower()
    completed = own_forces.get("completed") or {}
    townhall_count = sum(
        _number(count) for name, count in completed.items() if _asset_key(name) in TOWNHALL_KEYS
    )
    gas_structure_name = GAS_STRUCTURES.get(race_key)
    gas_structure_count = sum(
        _number(count)
        for name, count in completed.items()
        if gas_structure_name and _asset_key(name) == _asset_key(gas_structure_name)
    )
    bank_rising = bank_trend["minerals_delta"] is not None and bank_trend["minerals_delta"] >= 0
    resource_pressure = bool(
        (minerals >= 1000 and (bank_rising or minerals >= 2000))
        or (gas >= 800 and minerals >= 400)
    )
    target_mineral_commitment = (
        min(2000.0, max(400.0, minerals * 0.35))
        if resource_pressure
        else 0.0
    )
    combat = observation.get("combat") if isinstance(observation.get("combat"), dict) else {}
    predicted = str(combat.get("advantage_predicted") or "")
    army_advantage = str(combat.get("army_advantage") or "")
    disadvantage = "disadvantage" in f"{predicted} {army_advantage}".lower()
    task_decomposition = _build_task_decomposition(
        race=race_key,
        horizon=horizon,
        minerals=minerals,
        gas=gas,
        mineral_income=mineral_income,
        gas_income=gas_income,
        workers=workers,
        ideal_workers=ideal_workers,
        townhall_count=townhall_count,
        completed=completed,
        combat=combat,
        layer_profile=layer_profile,
        bank_rising=bank_rising,
    )
    production_capacity = task_decomposition["production_capacity"]
    # This is a feasible floor, not a wish to represent the entire bank in one
    # replacement queue.  The larger target remains visible to the assembler as
    # a soft objective.  Keeping the hard floor bounded prevents gas trimming,
    # the 20-item cap, and a large bank from becoming mutually impossible.
    minimum_mineral_commitment = min(
        target_mineral_commitment,
        max(0.0, _number(production_capacity.get("estimated_mobile_commands_this_horizon")) * 100.0),
    )
    minimum_strength_investment = (
        round(minimum_mineral_commitment * (0.8 if disadvantage else 0.6), 2)
        if minimum_mineral_commitment
        else 0.0
    )
    minimum_mobile_strength_investment = (
        round(minimum_strength_investment * (0.6 if disadvantage else 0.35), 2)
        if minimum_strength_investment
        else 0.0
    )
    committed_townhalls = sum(
        _number(count)
        for bucket_name in ("under_construction", "workers_en_route", "active_queues")
        for name, count in (own_forces.get(bucket_name) or {}).items()
        if any(key in _asset_key(name) for key in TOWNHALL_KEYS)
    )
    worker_ceiling = min(85.0, ideal_workers + min(1.0, committed_townhalls) * 4.0)
    raw_worker_gap = max(0, int(math.ceil(worker_ceiling - workers)))
    if task_decomposition["recovery_mode"]:
        worker_additions_allowed = min(raw_worker_gap, 6)
    elif task_decomposition["combat_emergency"]:
        # A completed expansion must not turn a 0-vs-army crisis into a twelve
        # worker queue, which was the direct Terran-vs-Zerg failure mode.
        worker_additions_allowed = min(raw_worker_gap, 2 if workers < ideal_workers * 0.65 else 0)
    else:
        worker_additions_allowed = raw_worker_gap
    gas_capacity_gap = bool(
        gas_structure_name
        and minerals >= 1500
        and gas < 350
        and gas_income < max(250.0, mineral_income * 0.22)
        and townhall_count > 0
        and gas_structure_count < townhall_count * 2
    )
    return {
        "race": race_key,
        "horizon_seconds": round(horizon, 2),
        "current": {
            "minerals": round(minerals, 2),
            "gas": round(gas, 2),
            "mineral_income_per_min": round(mineral_income, 2),
            "gas_income_per_min": round(gas_income, 2),
            "supply_used": round(supply_used, 2),
            "supply_cap": round(supply_cap, 2),
            "supply_free": round(supply_free, 2),
            "workers": round(workers, 2),
            "ideal_workers": round(ideal_workers, 2),
            "worker_saturation_ratio": round(workers / ideal_workers, 3) if ideal_workers else None,
            "army_supply": round(_number(economy.get("supply_army")), 2),
        },
        "projected_without_new_spending": {
            "minerals": round(minerals + mineral_income * horizon / 60.0, 2),
            "gas": round(gas + gas_income * horizon / 60.0, 2),
        },
        "bank_trend_since_previous_decision": bank_trend,
        "combat_state": {
            "army_advantage": combat.get("army_advantage"),
            "predicted_advantage": combat.get("advantage_predicted"),
            "income_advantage": combat.get("income_advantage"),
            "our_army_power": _number(combat.get("our_army_power")),
            "enemy_army_power": _number(combat.get("enemy_army_power")),
            "power_ratio": round(
                _number(combat.get("our_army_power")) / _number(combat.get("enemy_army_power")), 3
            ) if _number(combat.get("enemy_army_power")) else None,
        },
        "task_decomposition": task_decomposition,
        "attack_layer_profile": layer_profile,
        "resource_conversion_targets": {
            "minimum_mineral_commitment": round(minimum_mineral_commitment, 2),
            "target_mineral_commitment": round(target_mineral_commitment, 2),
            "minimum_strength_investment_minerals": minimum_strength_investment,
            "minimum_mobile_strength_investment_minerals": minimum_mobile_strength_investment,
            "worker_additions_allowed": worker_additions_allowed,
            "worker_ceiling": round(worker_ceiling, 2),
            "gas_capacity_gap": gas_capacity_gap,
            "recommended_gas_structure": gas_structure_name if gas_capacity_gap else None,
            "completed_gas_structures": gas_structure_count,
            "completed_townhalls": townhall_count,
        },
        "committed_and_available_assets": {
            "completed": own_forces.get("completed") or {},
            "under_construction": own_forces.get("under_construction") or {},
            "workers_en_route": own_forces.get("workers_en_route") or {},
            "active_queues": own_forces.get("active_queues") or {},
        },
        "completed_upgrades": list(observation.get("upgrades") or []),
        "enemy_evidence": {
            "composition": enemy.get("composition") or {},
            "last_observation_time": enemy.get("last_observation_time"),
            "seconds_since_last_seen": enemy.get("seconds_since_last_seen"),
            "enemy_air": combat.get("enemy_air"),
            "enemy_cloak_threat": bool(memory_flags.get("enemy_cloak_threat")),
        },
        "time_units": {
            "dataset_time": "game_loops",
            "game_loops_per_second": GAME_LOOPS_PER_SECOND,
        },
    }


def _can_attack(entity: dict[str, Any], layer: str) -> bool:
    wanted = str(layer).lower()
    for weapon in entity.get("weapons") or []:
        target = str((weapon or {}).get("target_type") or "").lower()
        if target in {"any", "both", wanted}:
            return True
    return False


def _combat_layer_profile(
    observation: dict[str, Any], *, data_path: str | Path
) -> dict[str, Any]:
    store = get_dataset_store(data_path)
    own_forces = observation.get("own_forces") if isinstance(observation.get("own_forces"), dict) else {}
    enemy = observation.get("enemy") if isinstance(observation.get("enemy"), dict) else {}
    own_rows = own_forces.get("completed") or {}
    enemy_rows = enemy.get("composition") or {}

    def summarize(rows: dict[str, Any]) -> dict[str, Any]:
        result = {
            "air_combat_supply": 0.0,
            "ground_combat_supply": 0.0,
            "anti_air_supply": 0.0,
            "anti_ground_supply": 0.0,
            "air_combat_units": [],
            "ground_combat_units": [],
        }
        for raw_name, raw_count in rows.items():
            count = _number(raw_count)
            entity = store.get_entity("Unit", str(raw_name))
            if not entity or count <= 0 or entity.get("is_worker") or entity.get("is_structure"):
                continue
            weapons = entity.get("weapons") or []
            unit_supply = _number(entity.get("supply"))
            if not weapons and unit_supply <= 0:
                continue
            name = str(entity.get("name") or raw_name)
            supply = max(0.5, unit_supply) * count
            layer_key = "air_combat_supply" if entity.get("is_flying") else "ground_combat_supply"
            names_key = "air_combat_units" if entity.get("is_flying") else "ground_combat_units"
            result[layer_key] += supply
            if name not in result[names_key]:
                result[names_key].append(name)
            if _can_attack(entity, "Air"):
                result["anti_air_supply"] += supply
            if _can_attack(entity, "Ground"):
                result["anti_ground_supply"] += supply
        for key in ("air_combat_supply", "ground_combat_supply", "anti_air_supply", "anti_ground_supply"):
            result[key] = round(result[key], 2)
        return result

    own = summarize(own_rows)
    foe = summarize(enemy_rows)
    required_anti_air = max(0.0, min(16.0, foe["air_combat_supply"] * 0.5) - own["anti_air_supply"])
    required_anti_ground = max(0.0, min(16.0, foe["ground_combat_supply"] * 0.35) - own["anti_ground_supply"])
    return {
        "own": own,
        "enemy": foe,
        "air_attack_gap": foe["air_combat_supply"] >= 4 and required_anti_air >= 2,
        "ground_attack_gap": foe["ground_combat_supply"] >= 6 and required_anti_ground >= 2,
        "required_anti_air_response_score": round(required_anti_air, 2),
        "required_anti_ground_response_score": round(required_anti_ground, 2),
    }


def planning_state_update(snapshot: dict[str, Any], game_time_seconds: float) -> dict[str, Any]:
    current = snapshot.get("current") or {}
    return {
        "game_time_seconds": float(game_time_seconds),
        "minerals": _number(current.get("minerals")),
        "gas": _number(current.get("gas")),
    }


def compact_ledger(ledger: dict[str, Any] | None) -> list[dict[str, Any]]:
    entries = (ledger or {}).get("facts") or {}
    compact: list[dict[str, Any]] = []
    for value in list(entries.values())[-MAX_LEDGER_ENTRIES:]:
        if not isinstance(value, dict):
            continue
        reply = value.get("reply") if isinstance(value.get("reply"), dict) else {}
        compact.append({
            "query_type": value.get("query_type"),
            "targets": value.get("targets") or [],
            "question": value.get("question"),
            "answer": reply.get("answer"),
            "confidence": reply.get("confidence"),
            "entities_mentioned": reply.get("entities_mentioned") or [],
        })
    return compact


def ledger_lookup(
    ledger: dict[str, Any] | None,
    question: str,
    query_type: str = "",
    targets: list[str] | None = None,
) -> dict[str, Any] | None:
    facts = (ledger or {}).get("facts") or {}
    value = facts.get(ledger_key(question, query_type, targets))
    return value if isinstance(value, dict) else None


def ledger_store(
    ledger: dict[str, Any],
    *,
    question: str,
    query_type: str,
    targets: list[str],
    reply: dict[str, Any],
) -> None:
    facts = ledger.setdefault("facts", {})
    facts[ledger_key(question, query_type, targets)] = {
        "question": question,
        "query_type": query_type,
        "targets": list(targets),
        "reply": reply,
    }
    while len(facts) > MAX_LEDGER_ENTRIES:
        del facts[next(iter(facts))]


def _entity_cost(entity: dict[str, Any], section: str) -> dict[str, float]:
    cost = entity.get("cost") if isinstance(entity.get("cost"), dict) else {}
    minerals = _number(entity.get("minerals")) or _number(cost.get("minerals"))
    gas = _number(entity.get("gas")) or _number(cost.get("gas"))
    raw_time = _number(entity.get("time")) or _number(cost.get("time"))
    return {
        "minerals": minerals,
        "gas": gas,
        # Structure records can carry inherited/cumulative supply values (for
        # example Lair).  They are not new unit supply demand.
        "supply": (
            _number(entity.get("supply"))
            if section == "Unit" and not entity.get("is_structure")
            else 0.0
        ),
        "time_loops": raw_time,
        "time_seconds": round(raw_time / GAME_LOOPS_PER_SECOND, 2) if raw_time else 0.0,
    }


def _asset_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _available_asset_keys(planning_snapshot: dict[str, Any]) -> set[str]:
    assets = planning_snapshot.get("committed_and_available_assets") or {}
    keys: set[str] = set()
    for bucket in assets.values():
        if not isinstance(bucket, dict):
            continue
        for name, count in bucket.items():
            if _number(count) > 0:
                keys.add(_asset_key(name))
    return keys


def _source_requirements(source: dict[str, Any], produced_section: str) -> list[str]:
    requirements: list[str] = []
    producer = source.get("producer") if isinstance(source.get("producer"), dict) else {}
    producer_name = str(producer.get("name") or "")
    # Workers and Larva are execution resources, not technology prerequisites.
    # Requiring a currently visible Larva would falsely reject otherwise legal
    # Zerg queues because Larva availability changes continuously.
    worker_producers = {"scv", "probe", "drone", "larva"}
    if produced_section == "Upgrade" or _asset_key(producer_name) not in worker_producers:
        if producer_name:
            requirements.append(producer_name)
    for requirement in source.get("requirements") or []:
        if not isinstance(requirement, dict):
            continue
        for key in ("building_name", "upgrade_name", "unit_name", "addon_name"):
            value = requirement.get(key)
            if value:
                value = str(value)
                if key == "addon_name" and value in {"TechLab", "Reactor"} and producer_name:
                    value = producer_name + value
                requirements.append(value)
    addon = source.get("required_addon")
    if addon:
        addon = str(addon)
        requirements.append(
            producer_name + addon
            if addon in {"TechLab", "Reactor"} and producer_name
            else addon
        )
    return list(dict.fromkeys(requirements))


def build_queue_audit(
    ordered_names: list[str],
    planning_snapshot: dict[str, Any],
    *,
    data_path: str | Path = DEFAULT_DATABASE_PATH,
) -> dict[str, Any]:
    store = get_dataset_store(data_path)
    rows: list[dict[str, Any]] = []
    unknown: list[str] = []
    totals = {"minerals": 0.0, "gas": 0.0, "listed_supply": 0.0}
    conversion = {
        "worker_count": 0,
        "worker_minerals": 0.0,
        "strength_minerals": 0.0,
        "strength_gas": 0.0,
        "mobile_strength_minerals": 0.0,
        "static_defense_minerals": 0.0,
        "anti_air_response_score": 0.0,
        "anti_ground_response_score": 0.0,
        "mobile_anti_air_response_score": 0.0,
        "mobile_anti_ground_response_score": 0.0,
    }
    providers = 0
    mobile_order_count = 0
    planned_production_additions = 0
    task_decomposition = planning_snapshot.get("task_decomposition") or {}
    capacity_plan = task_decomposition.get("production_capacity") or {}
    recommended_production = str(capacity_plan.get("recommended_structure") or "")
    available = _available_asset_keys(planning_snapshot)
    prerequisite_violations: list[dict[str, Any]] = []
    from .query.query_engine import query_reverse_production_sources

    for name in ordered_names:
        entity = store.get_entity("Unit", name)
        section = "Unit"
        if entity is None:
            entity = store.get_entity("Upgrade", name)
            section = "Upgrade"
        if entity is None:
            unknown.append(name)
            continue
        cost = _entity_cost(entity, section)
        race = entity.get("race")
        sources = query_reverse_production_sources(
            name,
            produced_section=section,
            producer_race=race,
            return_keys=["name", "race", "is_worker", "is_structure"],
            limit=20,
            data_path=data_path,
        ).get("results", [])
        requirement_options = [_source_requirements(source, section) for source in sources]
        if requirement_options:
            missing_options = [
                [required for required in option if _asset_key(required) not in available]
                for option in requirement_options
            ]
            if not any(not missing for missing in missing_options):
                best_missing = min(missing_options, key=len)
                prerequisite_violations.append({
                    "name": name,
                    "missing_before_item": best_missing,
                    "requirement_options": requirement_options,
                })
        totals["minerals"] += cost["minerals"]
        totals["gas"] += cost["gas"]
        is_worker = bool(entity.get("is_worker")) or name in WORKER_NAMES
        is_economy_structure = bool(entity.get("is_townhall")) or bool(entity.get("needs_geyser"))
        is_supply_provider = name in SUPPLY_PROVIDERS
        if is_worker:
            conversion["worker_count"] += 1
            conversion["worker_minerals"] += cost["minerals"]
        elif not is_economy_structure and not is_supply_provider:
            conversion["strength_minerals"] += cost["minerals"]
            conversion["strength_gas"] += cost["gas"]
            if section == "Unit" and not entity.get("is_structure") and cost["supply"] > 0:
                conversion["mobile_strength_minerals"] += cost["minerals"]
                mobile_order_count += 1
            elif section == "Unit" and entity.get("is_structure") and entity.get("weapons"):
                conversion["static_defense_minerals"] += cost["minerals"]
        if section == "Unit" and not is_worker:
            response_score = max(0.0, cost["supply"])
            if entity.get("is_structure") and entity.get("weapons"):
                response_score = max(4.0, response_score)
            if _can_attack(entity, "Air"):
                conversion["anti_air_response_score"] += response_score
                if not entity.get("is_structure"):
                    conversion["mobile_anti_air_response_score"] += response_score
            if _can_attack(entity, "Ground"):
                conversion["anti_ground_response_score"] += response_score
                if not entity.get("is_structure"):
                    conversion["mobile_anti_ground_response_score"] += response_score
        if name not in SUPPLY_PROVIDERS:
            totals["listed_supply"] += max(0.0, cost["supply"])
        else:
            providers += 1
        if recommended_production and _asset_key(name) == _asset_key(recommended_production):
            planned_production_additions += 1
        rows.append({"name": name, "section": section, **cost})
        available.add(_asset_key(name))
    budget = planning_snapshot.get("projected_without_new_spending") or {}
    free_supply = _number((planning_snapshot.get("current") or {}).get("supply_free"))
    projected_supply_free = free_supply + providers * SUPPLY_PROVIDER_BONUS - totals["listed_supply"]
    current_cap = _number((planning_snapshot.get("current") or {}).get("supply_cap"))
    target_buffer = recommended_supply_buffer(current_cap, min(24.0, totals["listed_supply"]))
    free_without_new_providers = free_supply - totals["listed_supply"]
    supply_overbuild_warning = (
        providers > 0
        and (current_cap >= 200 or free_without_new_providers >= target_buffer)
    )
    mineral_budget = _number(budget.get("minerals"))
    gas_budget = _number(budget.get("gas"))
    budget_overrun = {
        "minerals": round(totals["minerals"] - mineral_budget, 2)
        if mineral_budget and totals["minerals"] > mineral_budget * 1.25
        else 0.0,
        "gas": round(totals["gas"] - gas_budget, 2)
        if gas_budget and totals["gas"] > gas_budget * 1.5
        else 0.0,
    }
    targets = planning_snapshot.get("resource_conversion_targets") or {}
    minimum_mineral_commitment = _number(targets.get("minimum_mineral_commitment"))
    target_mineral_commitment = _number(targets.get("target_mineral_commitment"))
    minimum_strength_investment = _number(targets.get("minimum_strength_investment_minerals"))
    minimum_mobile_strength_investment = _number(
        targets.get("minimum_mobile_strength_investment_minerals")
    )
    worker_additions_allowed = int(_number(targets.get("worker_additions_allowed")))
    layer_profile = planning_snapshot.get("attack_layer_profile") or {}
    required_anti_air = _number(layer_profile.get("required_anti_air_response_score"))
    required_anti_ground = _number(layer_profile.get("required_anti_ground_response_score"))
    gas_structure = str(targets.get("recommended_gas_structure") or "")
    economic_and_strength_validation = {
        "mineral_commitment_shortfall": round(
            max(0.0, minimum_mineral_commitment - totals["minerals"]), 2
        ),
        "strength_investment_shortfall": round(
            max(0.0, minimum_strength_investment - conversion["strength_minerals"]), 2
        ),
        "mobile_strength_investment_shortfall": round(
            max(0.0, minimum_mobile_strength_investment - conversion["mobile_strength_minerals"]), 2
        ),
        "worker_overproduction": max(
            0, int(conversion["worker_count"]) - worker_additions_allowed
        ),
        "gas_capacity_gap_unaddressed": bool(
            gas_structure
            and not any(_asset_key(name) == _asset_key(gas_structure) for name in ordered_names)
        ),
        "recommended_gas_structure": gas_structure or None,
        "anti_air_response_shortfall": round(
            _response_shortfall(required_anti_air, conversion["anti_air_response_score"]), 2
        ) if layer_profile.get("air_attack_gap") else 0.0,
        "anti_ground_response_shortfall": round(
            _response_shortfall(required_anti_ground, conversion["anti_ground_response_score"]), 2
        ) if layer_profile.get("ground_attack_gap") else 0.0,
        "mobile_anti_air_response_shortfall": round(
            _response_shortfall(
                min(required_anti_air, max(4.0, required_anti_air * 0.5)),
                conversion["mobile_anti_air_response_score"],
            ), 2
        ) if layer_profile.get("air_attack_gap") else 0.0,
        "mobile_anti_ground_response_shortfall": round(
            _response_shortfall(
                min(required_anti_ground, max(4.0, required_anti_ground * 0.5)),
                conversion["mobile_anti_ground_response_score"],
            ), 2
        ) if layer_profile.get("ground_attack_gap") else 0.0,
        "queue_length_overflow": max(0, len(ordered_names) - 20),
    }
    return {
        "queue_length": len(ordered_names),
        "known_entity_count": len(rows),
        "unknown_names": unknown,
        "prerequisite_violations": prerequisite_violations,
        "planned_cost": {
            "minerals": round(totals["minerals"], 2),
            "gas": round(totals["gas"], 2),
            "listed_supply": round(totals["listed_supply"], 2),
        },
        "projected_budget": {
            "minerals": _number(budget.get("minerals")),
            "gas": _number(budget.get("gas")),
        },
        "budget_ratio": {
            "minerals": round(totals["minerals"] / _number(budget.get("minerals")), 3)
            if _number(budget.get("minerals")) else None,
            "gas": round(totals["gas"] / _number(budget.get("gas")), 3)
            if _number(budget.get("gas")) else None,
        },
        "budget_overrun": budget_overrun,
        "resource_and_strength_conversion": {
            **{key: round(value, 2) if isinstance(value, float) else value for key, value in conversion.items()},
            "targets": {
                "minimum_mineral_commitment": minimum_mineral_commitment,
                "target_mineral_commitment": target_mineral_commitment,
                "minimum_strength_investment_minerals": minimum_strength_investment,
                "minimum_mobile_strength_investment_minerals": minimum_mobile_strength_investment,
                "worker_additions_allowed": worker_additions_allowed,
                "required_anti_air_response_score": required_anti_air,
                "required_anti_ground_response_score": required_anti_ground,
            },
            "validation": economic_and_strength_validation,
        },
        "supply_projection": {
            "free_now": round(free_supply, 2),
            "providers_planned": providers,
            "provider_supply_added": round(providers * SUPPLY_PROVIDER_BONUS, 2),
            "listed_new_demand": round(totals["listed_supply"], 2),
            "estimated_free_after_listed_queue": round(projected_supply_free, 2),
            "target_buffer": target_buffer,
            "free_after_demand_without_new_providers": round(free_without_new_providers, 2),
            "overbuild_warning": supply_overbuild_warning,
            "limitation": "Listed supply is advisory; morphs, Zerg paired outputs, active queues, and completion timing require race-specific runtime interpretation.",
        },
        "execution_capacity": {
            "estimated_mobile_commands_this_horizon": int(_number(
                capacity_plan.get("estimated_mobile_commands_this_horizon")
            )),
            "planned_mobile_orders": mobile_order_count,
            "mobile_order_overflow": max(
                0,
                mobile_order_count - int(_number(
                    capacity_plan.get("estimated_mobile_commands_this_horizon")
                )),
            ),
            "production_capacity_gap": bool(capacity_plan.get("capacity_gap")),
            "recommended_production_structure": recommended_production or None,
            "recommended_production_additions": int(_number(
                capacity_plan.get("recommended_additions")
            )),
            "planned_production_additions": planned_production_additions,
        },
        "entity_costs": rows,
        "time_conversion": "dataset game loops divided by 22.4",
    }


def recommended_supply_buffer(supply_cap: float, production_burst_supply: float = 0.0) -> int:
    target = max(8.0, supply_cap * 0.1, production_burst_supply)
    return int(math.ceil(min(24.0, target)))


def normalize_queue_constraints(
    ordered_names: list[str],
    planning_snapshot: dict[str, Any],
    *,
    data_path: str | Path = DEFAULT_DATABASE_PATH,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Apply safe mechanical reductions before asking the model for semantic repair."""
    names = list(ordered_names)
    corrections: list[dict[str, Any]] = []
    targets = planning_snapshot.get("resource_conversion_targets") or {}
    workers_allowed = int(_number(targets.get("worker_additions_allowed")))
    kept_workers = 0
    filtered: list[str] = []
    removed_workers: list[str] = []
    for name in names:
        if name in WORKER_NAMES:
            if kept_workers >= workers_allowed:
                removed_workers.append(name)
                continue
            kept_workers += 1
        filtered.append(name)
    if removed_workers:
        corrections.append({"type": "remove_excess_workers", "names": removed_workers})
    names = filtered

    audit = build_queue_audit(names, planning_snapshot, data_path=data_path)
    if (audit.get("supply_projection") or {}).get("overbuild_warning"):
        removed_supply = [name for name in names if name in SUPPLY_PROVIDERS]
        names = [name for name in names if name not in SUPPLY_PROVIDERS]
        if removed_supply:
            corrections.append({"type": "remove_redundant_supply", "names": removed_supply})

    if len(names) > 20:
        corrections.append({"type": "truncate_queue", "names": names[20:]})
        names = names[:20]

    protected = str(targets.get("recommended_gas_structure") or "")
    for _ in range(20):
        audit = build_queue_audit(names, planning_snapshot, data_path=data_path)
        overrun = audit.get("budget_overrun") or {}
        resource = "gas" if _number(overrun.get("gas")) > 0 else (
            "minerals" if _number(overrun.get("minerals")) > 0 else ""
        )
        if not resource:
            break
        store = get_dataset_store(data_path)
        remove_index = None
        for index in range(len(names) - 1, -1, -1):
            name = names[index]
            if protected and _asset_key(name) == _asset_key(protected):
                continue
            entity = store.get_entity("Unit", name)
            section = "Unit"
            if entity is None:
                entity = store.get_entity("Upgrade", name)
                section = "Upgrade"
            if entity and _entity_cost(entity, section)[resource] > 0:
                remove_index = index
                break
        if remove_index is None:
            break
        removed = names.pop(remove_index)
        corrections.append({"type": f"trim_{resource}_overrun", "name": removed})
    return names, corrections


def stabilize_queue_constraints(
    ordered_names: list[str],
    planning_snapshot: dict[str, Any],
    *,
    data_path: str | Path = DEFAULT_DATABASE_PATH,
    knowledge_preferences: list[str] | None = None,
    knowledge_preferences_by_layer: dict[str, list[str]] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Assemble a safe executable queue after semantic MainAgent planning.

    Numeric targets are handled here instead of being bounced through repeated
    LLM validation turns.  The routine never invents a full strategy: it keeps
    valid semantic items, removes unexecutable tails, adds at most the harness
    recommended production, and fills spare near-term throughput with a
    race-native unit that is already legal.
    """

    names, corrections = normalize_queue_constraints(
        ordered_names, planning_snapshot, data_path=data_path
    )

    # Remove items whose canonical record or prerequisite path is unavailable.
    # Revalidate after each removal because an earlier bad item may itself have
    # been the claimed prerequisite for a later one.
    for _ in range(24):
        audit = build_queue_audit(names, planning_snapshot, data_path=data_path)
        bad_names = list(audit.get("unknown_names") or [])
        violations = audit.get("prerequisite_violations") or []
        if violations:
            bad_names.append(str(violations[0].get("name") or ""))
        bad_name = next((item for item in bad_names if item), "")
        if not bad_name:
            break
        remove_index = next(
            (index for index in range(len(names) - 1, -1, -1) if names[index] == bad_name),
            None,
        )
        if remove_index is None:
            break
        removed = names.pop(remove_index)
        corrections.append({"type": "remove_unexecutable_item", "name": removed})

    tasks = planning_snapshot.get("task_decomposition") or {}
    capacity = tasks.get("production_capacity") or {}
    recommended_production = str(capacity.get("recommended_structure") or "")
    production_needed = int(_number(capacity.get("recommended_additions")))

    def candidate_is_safe(candidate_names: list[str]) -> bool:
        candidate_audit = build_queue_audit(
            candidate_names, planning_snapshot, data_path=data_path
        )
        overrun = candidate_audit.get("budget_overrun") or {}
        return bool(
            not candidate_audit.get("unknown_names")
            and not candidate_audit.get("prerequisite_violations")
            and not any(_number(value) > 0 for value in overrun.values())
            and len(candidate_names) <= 20
        )

    # Expand real spending throughput before adding a long unit wish list.
    if recommended_production and production_needed > 0:
        already = sum(
            1 for name in names if _asset_key(name) == _asset_key(recommended_production)
        )
        for _ in range(max(0, production_needed - already)):
            candidate = names + [recommended_production]
            if not candidate_is_safe(candidate):
                break
            names = candidate
            corrections.append({
                "type": "add_production_capacity",
                "name": recommended_production,
            })

    targets = planning_snapshot.get("resource_conversion_targets") or {}
    recommended_gas = str(targets.get("recommended_gas_structure") or "")
    if recommended_gas and not any(
        _asset_key(name) == _asset_key(recommended_gas) for name in names
    ):
        candidate = names + [recommended_gas]
        if candidate_is_safe(candidate):
            names = candidate
            corrections.append({"type": "add_required_gas_capacity", "name": recommended_gas})

    fallback = tasks.get("fallback_units") or {}
    layer = planning_snapshot.get("attack_layer_profile") or {}
    verified_preferences = list(dict.fromkeys(
        str(item) for item in (knowledge_preferences or []) if str(item)
    ))
    fallback_candidates: list[str] = list(verified_preferences)
    if layer.get("air_attack_gap"):
        fallback_candidates.extend(fallback.get("anti_air") or [])
    if layer.get("ground_attack_gap"):
        fallback_candidates.extend(fallback.get("anti_ground") or [])
    fallback_candidates.extend(fallback.get("mineral_sink") or [])
    fallback_candidates = list(dict.fromkeys(str(item) for item in fallback_candidates if item))

    # LLMs tend to collapse a mixed enemy composition into one universal unit
    # type.  Verified knowledge is more useful when it supplies a small
    # portfolio.  Promote one executable candidate for each actual attack-layer
    # gap to the front of the mobile work, while retaining the rest of the
    # strategy queue.  This is ordering, not an invented build order.
    layer_preferences = knowledge_preferences_by_layer or {}
    required_layer_preferences: list[tuple[str, list[str]]] = []
    if layer.get("air_attack_gap"):
        required_layer_preferences.append(("air", list(layer_preferences.get("air") or [])))
    if layer.get("ground_attack_gap"):
        required_layer_preferences.append(("ground", list(layer_preferences.get("ground") or [])))
    insertion_index = 0
    provider_names = {_asset_key(name) for name in SUPPLY_PROVIDERS}
    while insertion_index < len(names) and _asset_key(names[insertion_index]) in provider_names:
        insertion_index += 1
    for layer_name, candidates in required_layer_preferences:
        preferred_name = next(
            (name for name in candidates if candidate_is_safe([name])),
            None,
        )
        if not preferred_name:
            continue
        existing_index = next(
            (index for index, name in enumerate(names) if _asset_key(name) == _asset_key(preferred_name)),
            None,
        )
        if existing_index is None:
            candidate = names[:insertion_index] + [preferred_name] + names[insertion_index:]
            if not candidate_is_safe(candidate):
                continue
            names = candidate
            corrections.append({
                "type": "insert_verified_layer_response",
                "layer": layer_name,
                "name": preferred_name,
            })
        elif existing_index > insertion_index:
            names.insert(insertion_index, names.pop(existing_index))
            corrections.append({
                "type": "promote_verified_layer_response",
                "layer": layer_name,
                "name": preferred_name,
            })
        insertion_index += 1

    target_minerals = _number(targets.get("target_mineral_commitment"))
    if tasks.get("combat_emergency") or tasks.get("attack_layer_gap"):
        target_minerals = max(400.0, target_minerals)
    mobile_cap = int(_number(capacity.get("estimated_mobile_commands_this_horizon")))
    should_fill = bool(
        tasks.get("resource_overflow")
        or tasks.get("combat_emergency")
        or tasks.get("attack_layer_gap")
    )
    if should_fill and target_minerals > 0 and fallback_candidates:
        minimum_mobile_minerals = _number(
            targets.get("minimum_mobile_strength_investment_minerals")
        )
        for _ in range(20):
            audit = build_queue_audit(names, planning_snapshot, data_path=data_path)
            conversion = audit.get("resource_and_strength_conversion") or {}
            if (
                _number((audit.get("planned_cost") or {}).get("minerals")) >= target_minerals
                and _number(conversion.get("mobile_strength_minerals"))
                >= minimum_mobile_minerals
            ):
                break
            if int(_number((audit.get("execution_capacity") or {}).get("planned_mobile_orders"))) >= mobile_cap:
                break
            added = None
            for candidate_name in fallback_candidates:
                candidate = names + [candidate_name]
                if candidate_is_safe(candidate):
                    names = candidate
                    added = candidate_name
                    break
            if not added:
                break
            corrections.append({
                "type": (
                    "fill_verified_knowledge_response"
                    if added in verified_preferences
                    else "fill_executable_mobile_capacity"
                ),
                "name": added,
            })

    # Cover the assembled unit burst, not the bank.  Supply is inserted before
    # the new work so a long unit list cannot sit behind a supply block.
    audit = build_queue_audit(names, planning_snapshot, data_path=data_path)
    supply = audit.get("supply_projection") or {}
    current = planning_snapshot.get("current") or {}
    cap_room = max(0.0, 200.0 - _number(current.get("supply_cap")))
    missing_supply = max(
        0.0,
        _number(supply.get("listed_new_demand"))
        + min(16.0, _number(supply.get("target_buffer")))
        - _number(supply.get("free_now"))
        - _number(supply.get("provider_supply_added")),
    )
    provider = {
        "terran": "SupplyDepot", "protoss": "Pylon", "zerg": "Overlord"
    }.get(str(planning_snapshot.get("race") or "").lower())
    additions = min(3, int(math.ceil(min(missing_supply, cap_room) / SUPPLY_PROVIDER_BONUS)))
    if provider and additions > 0:
        for _ in range(additions):
            candidate = [provider] + names
            if not candidate_is_safe(candidate):
                break
            names = candidate
            corrections.append({"type": "add_required_supply", "name": provider})

    return names, corrections


__all__ = [
    "GAME_LOOPS_PER_SECOND",
    "build_planning_snapshot",
    "build_queue_audit",
    "compact_ledger",
    "ledger_lookup",
    "ledger_key",
    "ledger_store",
    "normalize_question",
    "normalize_queue_constraints",
    "stabilize_queue_constraints",
    "planning_state_update",
    "recommended_supply_buffer",
]
