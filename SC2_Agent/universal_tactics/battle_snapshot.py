"""Live tactical state extracted from existing Sharpy managers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

from sharpy.general.extended_power import ExtendedPower
from sharpy.interfaces import IGameAnalyzer, IZoneManager
from sharpy.managers.extensions.game_states.advantage import Advantage

from .composition import siege_power_from_units
from .config import DEFAULT_CONFIG, UniversalTacticalConfig


@dataclass(frozen=True)
class BattleSnapshot:
    game_time: float = 0.0
    own_total_power: float = 0.0
    enemy_known_power: float = 0.0
    enemy_predicted_power: float = 0.0

    own_ground_power: float = 0.0
    own_air_power: float = 0.0
    own_ground_presence: float = 0.0
    own_air_presence: float = 0.0
    enemy_ground_power: float = 0.0
    enemy_air_power: float = 0.0
    enemy_ground_presence: float = 0.0
    enemy_air_presence: float = 0.0

    own_melee_power: float = 0.0
    own_siege_power: float = 0.0
    own_detector_count: int = 0
    own_stealth_power: float = 0.0
    enemy_melee_power: float = 0.0
    enemy_siege_power: float = 0.0
    enemy_detector_count: int = 0
    enemy_stealth_power: float = 0.0

    army_advantage: Advantage = Advantage.Even
    predicted_army_advantage: Advantage = Advantage.Even
    income_advantage: Advantage = Advantage.Even
    supply_used: float = 0.0
    supply_cap: float = 0.0
    army_supply: float = 0.0

    threatened_zone_count: int = 0
    max_local_enemy_power: float = 0.0
    max_local_own_defender_power: float = 0.0
    largest_army_group_power: float = 0.0
    largest_army_group_fraction: float = 0.0
    enemy_static_defense_target_power: float = 0.0
    proxy_detected: bool = False

    def trace_view(self):
        return {
            "own_total_power": round(self.own_total_power, 3),
            "enemy_predicted_power": round(self.enemy_predicted_power, 3),
            "predicted_army_advantage": self.predicted_army_advantage.name,
            "income_advantage": self.income_advantage.name,
            "largest_army_group_fraction": round(self.largest_army_group_fraction, 3),
            "supply_used": self.supply_used,
            "threatened_zone_count": self.threatened_zone_count,
            "own_air_power": round(self.own_air_power, 3),
            "enemy_air_presence": round(self.enemy_air_presence, 3),
            "own_detector_count": self.own_detector_count,
            "enemy_stealth_power": round(self.enemy_stealth_power, 3),
        }


class BattleSnapshotBuilder:
    """Adapter over GameAnalyzer, zones and roles; it does not own another model."""

    def __init__(self, config: UniversalTacticalConfig = DEFAULT_CONFIG):
        self.config = config
        self.knowledge = None

    async def start(self, knowledge):
        self.knowledge = knowledge
        self.ai = knowledge.ai
        self.roles = knowledge.roles
        self.unit_values = knowledge.unit_values
        self.zone_manager = knowledge.get_required_manager(IZoneManager)
        self.game_analyzer = knowledge.get_required_manager(IGameAnalyzer)

    def _combat_units(self) -> List:
        worker_type = self.knowledge.my_worker_type
        return list(
            self.ai.units.filter(
                lambda unit: unit.is_ready
                and unit.type_id != worker_type
                and self.unit_values.should_attack(unit)
            )
        )

    def _largest_group(self, units: List, total_power: float):
        if not units or total_power <= 0:
            return 0.0, 0.0
        remaining = set(range(len(units)))
        largest = 0.0
        link = self.config.cohesion_link_distance
        while remaining:
            seed = remaining.pop()
            stack = [seed]
            group_power = 0.0
            while stack:
                index = stack.pop()
                current = units[index]
                group_power += float(self.unit_values.power(current))
                linked = [
                    other
                    for other in remaining
                    if current.position.distance_to(units[other].position) <= link
                ]
                for other in linked:
                    remaining.remove(other)
                    stack.append(other)
            largest = max(largest, group_power)
        return largest, min(1.0, largest / max(total_power, 1e-9))

    def _zone_state(self):
        threatened = 0
        max_enemy = 0.0
        max_defender = 0.0
        static_target = 0.0
        our_main = self.zone_manager.own_main_zone.center_location
        proxy = bool(self.ai.enemy_structures.closer_than(70, our_main))
        for zone in self.zone_manager.expansion_zones:
            enemy_power = float(getattr(zone.assaulting_enemy_power, "power", 0.0))
            if (zone.is_ours or zone == self.zone_manager.own_main_zone) and enemy_power > self.config.meaningful_zone_threat_power:
                threatened += 1
                max_enemy = max(max_enemy, enemy_power)
                own = ExtendedPower(self.unit_values)
                own.add_units(zone.our_units.filter(lambda unit: self.unit_values.should_attack(unit)))
                max_defender = max(max_defender, own.power)
            if zone.is_enemys:
                static_target = max(static_target, float(zone.enemy_static_power.power))
        return threatened, max_enemy, max_defender, static_target, proxy

    def build(self) -> BattleSnapshot:
        analyzer = self.game_analyzer
        own = analyzer.our_power
        known = analyzer.enemy_power
        predicted = analyzer.enemy_predict_power
        units = self._combat_units()
        largest, fraction = self._largest_group(units, float(own.power))
        threatened, local_enemy, local_own, static_target, proxy = self._zone_state()
        return BattleSnapshot(
            game_time=float(self.ai.time),
            own_total_power=float(own.power),
            enemy_known_power=float(known.power),
            enemy_predicted_power=float(predicted.power),
            own_ground_power=float(own.ground_power),
            own_air_power=float(own.air_power),
            own_ground_presence=float(own.ground_presence),
            own_air_presence=float(own.air_presence),
            enemy_ground_power=float(predicted.ground_power),
            enemy_air_power=float(predicted.air_power),
            enemy_ground_presence=float(predicted.ground_presence),
            enemy_air_presence=float(predicted.air_presence),
            own_melee_power=float(own.melee_power),
            own_siege_power=siege_power_from_units(units, self.unit_values),
            own_detector_count=int(own.detectors),
            own_stealth_power=float(own.stealth_power),
            enemy_melee_power=float(predicted.melee_power),
            # V1 does not consume predicted siege fraction. The legacy
            # ExtendedPower field overwrites instead of accumulates, and
            # predicted unit instances are not reliably exposed here.
            enemy_siege_power=0.0,
            enemy_detector_count=int(predicted.detectors),
            enemy_stealth_power=float(predicted.stealth_power),
            army_advantage=analyzer.our_army_advantage,
            predicted_army_advantage=analyzer.our_army_predict,
            income_advantage=analyzer.our_income_advantage,
            supply_used=float(self.ai.supply_used),
            supply_cap=float(self.ai.supply_cap),
            army_supply=float(self.ai.supply_army),
            threatened_zone_count=threatened,
            max_local_enemy_power=local_enemy,
            max_local_own_defender_power=local_own,
            largest_army_group_power=largest,
            largest_army_group_fraction=fraction,
            enemy_static_defense_target_power=static_target,
            proxy_detected=proxy,
        )
