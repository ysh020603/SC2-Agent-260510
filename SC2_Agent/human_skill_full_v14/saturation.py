from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math
import re

from SC2_Agent.data_tools import (
    action_candidates_for_entity,
    canonical_race_entity_name,
    race_mechanics,
    race_unit_names,
)
from SC2_Agent.data_tools.sc2_data_common import build_entity_indexes, load_database


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

    @property
    def bank(self) -> int:
        return self.minerals + self.gas


@dataclass(frozen=True)
class CombatProfile:
    name: str
    minerals: int
    gas: int
    supply: float
    executors: tuple[str, ...]

    @property
    def total_cost(self) -> int:
        return self.minerals + self.gas


@lru_cache(maxsize=1)
def _units() -> dict:
    units, _ = build_entity_indexes(load_database())
    return units


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
    entities = frozenset(
        name.upper() for name in re.findall(r"\b[0-9]+\s+([A-Z][A-Z0-9_]*)\b", own_text)
    )
    return LiveState(
        minerals=int(resource.group(1)),
        gas=int(resource.group(2)),
        mineral_income=float(income.group(1)) if income else 0.0,
        gas_income=float(income.group(2)) if income else 0.0,
        used_supply=float(supply.group(1)),
        supply_cap=float(supply.group(2)),
        army_supply=float(supply.group(3)),
        own_entities=entities,
    )


def conversion_alert(obs_text: str, game_time_seconds: float) -> str:
    state = parse_live_state(obs_text)
    if state is None:
        return ""
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
    if item.get("is_structure") or item.get("is_worker"):
        return None
    supply = float(item.get("supply") or 0) * max(1, int(candidate.output_count))
    if supply <= 0:
        return None
    return CombatProfile(
        name=name,
        minerals=int(item.get("minerals") or 0) * max(1, int(candidate.output_count)),
        gas=int(item.get("gas") or 0) * max(1, int(candidate.output_count)),
        supply=supply,
        executors=tuple(candidate.executors),
    )


def _reachable(profile: CombatProfile, state: LiveState) -> bool:
    return any(executor.upper() in state.own_entities for executor in profile.executors)


def _candidate_profiles(
    race: str,
    state: LiveState,
    ordered_names: list[str],
    knowledge_candidates: list[str],
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
        if profiles:
            # Prefer the model queue, then the matched human/knowledge node. The
            # full race catalog is only a final reachability fallback.
            break
    return profiles[:3]


def _supply_gain(race: str) -> float:
    provider = race_mechanics(race).supply_provider
    item = _units().get(provider) or {}
    return max(1.0, -float(item.get("supply") or -8.0))


def saturate_combat_queue(
    *,
    race: str,
    obs_text: str,
    ordered_names: list[str],
    knowledge_candidates: list[str],
    game_time_seconds: float,
    rotation: int = 0,
) -> list[str]:
    """Front-load a supply-safe combat batch when live execution is under-converting resources.

    The implementation contains no matchup or unit-name rules. Candidate roles,
    executors, costs, and supply all come from the bundled SC2 database.
    """

    state = parse_live_state(obs_text)
    if state is None or not conversion_alert(obs_text, game_time_seconds):
        return list(ordered_names)
    profiles = _candidate_profiles(race, state, list(ordered_names), list(knowledge_candidates))
    if not profiles:
        return list(ordered_names)
    rotation %= len(profiles)
    profiles = profiles[rotation:] + profiles[:rotation]

    target_spend = min(1600, max(600, int(state.bank * 0.55)))
    batch: list[CombatProfile] = []
    planned_spend = 0
    index = 0
    while len(batch) < 14 and (len(batch) < 6 or planned_spend < target_spend):
        profile = profiles[index % len(profiles)]
        batch.append(profile)
        planned_spend += max(50, profile.total_cost)
        index += 1

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
    providers_needed = max(0, int(math.ceil(max(0.0, demand - free_supply) / _supply_gain(race))))
    provider_capacity = int(max(0.0, 200.0 - state.supply_cap) // _supply_gain(race))
    providers_needed = min(providers_needed, provider_capacity)
    return [provider] * providers_needed + [profile.name for profile in fitted]
