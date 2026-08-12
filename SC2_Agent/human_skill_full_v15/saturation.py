from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
import re

from SC2_Agent.data_tools import (
    action_candidates_for_entity,
    canonical_race_entity_name,
    check_action_prerequisites,
    race_mechanics,
    race_unit_names,
)
from SC2_Agent.data_tools.sc2_data_common import (
    ADDON_EXECUTOR_TO_HOST,
    build_entity_indexes,
    load_database,
)


@dataclass(frozen=True)
class LiveState:
    minerals: int
    gas: int
    mineral_income: float
    gas_income: float
    used_supply: float
    supply_cap: float
    army_supply: float
    own_entities: frozenset[str]
    own_counts: tuple[tuple[str, int], ...]

    @property
    def bank(self) -> int:
        return self.minerals + self.gas

    def count(self, name: str) -> int:
        key = name.upper()
        return dict(self.own_counts).get(key, 0)


@dataclass(frozen=True)
class CombatProfile:
    name: str
    ability_name: str
    minerals: int
    gas: int
    supply: float
    executors: tuple[str, ...]
    target_domains: frozenset[str]

    @property
    def total_cost(self) -> int:
        return self.minerals + self.gas


@lru_cache(maxsize=1)
def _units() -> dict:
    units, _ = build_entity_indexes(load_database())
    return units


@lru_cache(maxsize=1)
def _folded_units() -> dict[str, dict]:
    return {name.upper(): item for name, item in _units().items()}


def parse_live_state(obs_text: str) -> LiveState | None:
    resource = re.search(r"\[Economy\]\s*([0-9]+) minerals,\s*([0-9]+) vespene", obs_text, re.I)
    income = re.search(r"income\s*([0-9.]+) mins/min,\s*([0-9.]+) gas/min", obs_text, re.I)
    supply = re.search(
        r"Supply:\s*([0-9.]+)\s*/\s*([0-9.]+)\s*\(workers.*?army\s*([0-9.]+)\)",
        obs_text,
        re.I,
    )
    if not resource or not supply:
        return None
    own_text = obs_text.split("[Enemy Intelligence]", 1)[0]
    counts: dict[str, int] = {}
    for raw_count, raw_name in re.findall(r"\b([0-9]+)\s+([A-Z][A-Z0-9_]*)\b", own_text):
        name = raw_name.upper()
        counts[name] = counts.get(name, 0) + int(raw_count)
    return LiveState(
        minerals=int(resource.group(1)),
        gas=int(resource.group(2)),
        mineral_income=float(income.group(1)) if income else 0.0,
        gas_income=float(income.group(2)) if income else 0.0,
        used_supply=float(supply.group(1)),
        supply_cap=float(supply.group(2)),
        army_supply=float(supply.group(3)),
        own_entities=frozenset(counts),
        own_counts=tuple(sorted(counts.items())),
    )


def conversion_alert(obs_text: str, game_time_seconds: float) -> str:
    state = parse_live_state(obs_text)
    if state is None:
        return ""
    if game_time_seconds >= 180 and state.bank >= 500 and state.army_supply < 8:
        return "an early unspent bank with insufficient immediate defense"
    if game_time_seconds >= 300 and state.bank >= 750 and state.army_supply < 15:
        return "a large bank with critically low army supply"
    if game_time_seconds >= 600 and state.bank >= 1500 and state.army_supply < 30:
        return "a persistent large bank with low army supply"
    if game_time_seconds >= 600 and state.bank >= 2500 and state.used_supply < 180:
        return "a severe unspent bank while usable supply remains"
    return ""


def _combat_profile(race: str, raw_name: str) -> CombatProfile | None:
    name = canonical_race_entity_name(race, raw_name)
    if not name:
        return None
    candidates = action_candidates_for_entity(race, name)
    if not candidates:
        return None
    candidate = candidates[0]
    item = _units().get(candidate.target_result) or {}
    weapons = item.get("weapons") or []
    if item.get("is_structure") or item.get("is_worker") or not weapons:
        return None
    supply = float(item.get("supply") or 0) * max(1, int(candidate.output_count))
    if supply <= 0:
        return None
    domains = frozenset(str(weapon.get("target_type") or "").lower() for weapon in weapons)
    return CombatProfile(
        name=name,
        ability_name=candidate.ability_name,
        minerals=int(item.get("minerals") or 0) * max(1, int(candidate.output_count)),
        gas=int(item.get("gas") or 0) * max(1, int(candidate.output_count)),
        supply=supply,
        executors=tuple(candidate.executors),
        target_domains=domains,
    )


def _reachable(profile: CombatProfile, state: LiveState) -> bool:
    report = check_action_prerequisites(list(state.own_entities), [profile.ability_name])
    rows = report.get("ordered_reports") or []
    return bool(rows and rows[0].get("available"))


def _enemy_domain(obs_text: str) -> str:
    enemy_text = obs_text.split("[Enemy Intelligence]", 1)[1] if "[Enemy Intelligence]" in obs_text else ""
    has_air = False
    has_ground = False
    for raw_name in re.findall(r"\b[0-9]+\s+([A-Z][A-Z0-9_]*)\b", enemy_text):
        item = _folded_units().get(raw_name.upper()) or {}
        if item.get("is_structure") or item.get("is_worker"):
            continue
        has_air = has_air or bool(item.get("is_flying"))
        has_ground = has_ground or not bool(item.get("is_flying"))
    if has_air:
        return "air"
    if has_ground:
        return "ground"
    return ""


def _can_attack(profile: CombatProfile, domain: str) -> bool:
    if not domain:
        return True
    return domain in profile.target_domains or "any" in profile.target_domains


def _candidate_profiles(
    race: str,
    state: LiveState,
    ordered_names: list[str],
    knowledge_candidates: list[str],
    enemy_domain: str,
) -> list[CombatProfile]:
    profiles: list[CombatProfile] = []
    seen: set[str] = set()
    for source in (ordered_names, knowledge_candidates, race_unit_names(race)):
        for raw_name in source:
            profile = _combat_profile(race, raw_name)
            if profile is None or profile.name in seen:
                continue
            if profile.gas > state.gas + state.gas_income or profile.minerals > state.minerals + state.mineral_income:
                continue
            if not _reachable(profile, state):
                continue
            profiles.append(profile)
            seen.add(profile.name)
            if len(profiles) >= 6:
                break
        if len(profiles) >= 6:
            break
    compatible = [profile for profile in profiles if _can_attack(profile, enemy_domain)]
    return (compatible or profiles)[:3]


def _supply_gain(race: str) -> float:
    provider = race_mechanics(race).supply_provider
    item = _units().get(provider) or {}
    return max(1.0, -float(item.get("supply") or -8.0))


def _build_batch(state: LiveState, profiles: list[CombatProfile]) -> list[CombatProfile]:
    mineral_budget = state.minerals + int(state.mineral_income * 0.75)
    gas_budget = state.gas + int(state.gas_income * 0.75)
    target_spend = min(1800, max(600, int(state.bank * 0.6)))
    batch: list[CombatProfile] = []
    spent_minerals = spent_gas = 0
    cursor = 0
    misses = 0
    while len(batch) < 14 and (len(batch) < 6 or spent_minerals + spent_gas < target_spend):
        profile = profiles[cursor % len(profiles)]
        cursor += 1
        if spent_minerals + profile.minerals > mineral_budget or spent_gas + profile.gas > gas_budget:
            misses += 1
            if misses >= len(profiles) * 2:
                break
            continue
        misses = 0
        batch.append(profile)
        spent_minerals += profile.minerals
        spent_gas += profile.gas
    return batch


def _buildable_producer(race: str, profiles: list[CombatProfile]) -> str:
    for profile in profiles:
        for executor in profile.executors:
            host = ADDON_EXECUTOR_TO_HOST.get(executor, executor)
            item = _units().get(host) or {}
            candidates = action_candidates_for_entity(race, host)
            if item.get("is_structure") and any(c.execution_mode == "worker_build" for c in candidates):
                return host
    return ""


def _parallel_producer_repair(race: str, state: LiveState, profiles: list[CombatProfile], batch_size: int) -> list[str]:
    if state.bank < 900 or batch_size < 6:
        return []
    producer = _buildable_producer(race, profiles)
    if not producer:
        return []
    existing = state.count(producer)
    desired = min(4, max(2, int(math.ceil(batch_size / 4))))
    missing = min(2, max(0, desired - existing))
    cost = _units().get(producer) or {}
    if int(cost.get("minerals") or 0) * missing > state.minerals:
        missing = max(0, state.minerals // max(1, int(cost.get("minerals") or 1)))
    return [producer] * missing


def _is_shared_renewable_executor(profile: CombatProfile) -> bool:
    for executor in profile.executors:
        item = _units().get(executor) or {}
        if (
            not item.get("is_structure")
            and not item.get("is_worker")
            and float(item.get("supply") or 0) == 0
            and int(item.get("minerals") or 0) == 0
            and int(item.get("gas") or 0) == 0
        ):
            return True
    return False


def _renewable_resource_repair(race: str, state: LiveState, main_profiles: list[CombatProfile]) -> list[str]:
    if not any(_is_shared_renewable_executor(profile) for profile in main_profiles):
        return []
    mechanics = race_mechanics(race)
    support = []
    for name in race_unit_names(race):
        profile = _combat_profile(race, name)
        if profile and _reachable(profile, state) and any((_units().get(executor) or {}).get("is_structure") for executor in profile.executors):
            support.append(profile)
    repairs = [support[0].name] * 2 if support else []
    townhall = mechanics.townhall
    townhall_candidates = action_candidates_for_entity(race, townhall)
    townhall_cost = _units().get(townhall) or {}
    if (
        state.bank >= 1000
        and state.count(townhall) < 3
        and int(townhall_cost.get("minerals") or 0) <= state.minerals
        and any(candidate.execution_mode == "expand" for candidate in townhall_candidates)
    ):
        repairs.append(townhall)
    return repairs


def saturate_combat_queue(
    *,
    race: str,
    obs_text: str,
    ordered_names: list[str],
    knowledge_candidates: list[str],
    game_time_seconds: float,
    rotation: int = 0,
) -> list[str]:
    """Repair resource conversion through generic action, target, and production knowledge."""

    state = parse_live_state(obs_text)
    if state is None or not conversion_alert(obs_text, game_time_seconds):
        return list(ordered_names)
    profiles = _candidate_profiles(
        race,
        state,
        list(ordered_names),
        list(knowledge_candidates),
        _enemy_domain(obs_text),
    )
    if not profiles:
        return list(ordered_names)
    rotation %= len(profiles)
    profiles = profiles[rotation:] + profiles[:rotation]
    batch = _build_batch(state, profiles)
    if not batch:
        return list(ordered_names)

    free_supply = max(0.0, state.supply_cap - state.used_supply)
    max_future_supply = max(0.0, 200.0 - state.used_supply)
    fitted: list[CombatProfile] = []
    demand = 0.0
    for profile in batch:
        if demand + profile.supply > max_future_supply + 1e-6:
            break
        fitted.append(profile)
        demand += profile.supply
    if not fitted:
        return list(ordered_names)

    provider = race_mechanics(race).supply_provider
    gain = _supply_gain(race)
    providers_needed = max(0, int(math.ceil(max(0.0, demand - free_supply) / gain)))
    provider_capacity = int(max(0.0, 200.0 - state.supply_cap) // gain)
    providers = [provider] * min(providers_needed, provider_capacity)

    immediate_count = min(4, len(fitted))
    immediate = [profile.name for profile in fitted[:immediate_count]]
    remaining = [profile.name for profile in fitted[immediate_count:]]
    production_repairs = _parallel_producer_repair(race, state, profiles, len(fitted))
    renewable_repairs = _renewable_resource_repair(race, state, profiles)
    return (providers + immediate + production_repairs + renewable_repairs + remaining)[:30]
