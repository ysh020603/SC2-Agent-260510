"""Explainable, race-neutral attack readiness condition tree."""

from __future__ import annotations

from dataclasses import dataclass

from sharpy.managers.extensions.game_states.advantage import Advantage

from .battle_snapshot import BattleSnapshot
from .config import DEFAULT_CONFIG, UniversalTacticalConfig


@dataclass(frozen=True)
class ReadinessDecision:
    should_attack: bool
    reason: str
    composition_safe: bool
    composition_block_reason: str = ""


def composition_safety(snapshot: BattleSnapshot, config: UniversalTacticalConfig = DEFAULT_CONFIG):
    enemy_total = max(snapshot.enemy_predicted_power, snapshot.enemy_known_power, 1e-9)
    enemy_air_fraction = snapshot.enemy_air_presence / enemy_total
    if enemy_air_fraction >= config.enemy_air_fraction_gate:
        coverage = snapshot.own_air_power / max(snapshot.enemy_air_presence, 1e-9)
        if coverage < config.min_anti_air_coverage_ratio:
            return False, "insufficient_anti_air_coverage"

    enemy_ground_fraction = snapshot.enemy_ground_presence / enemy_total
    if enemy_ground_fraction >= config.enemy_ground_fraction_gate:
        coverage = snapshot.own_ground_power / max(snapshot.enemy_ground_presence, 1e-9)
        if coverage < config.min_anti_ground_coverage_ratio:
            return False, "insufficient_anti_ground_coverage"

    if (
        config.block_attack_without_detection
        and snapshot.enemy_stealth_power > 0
        and snapshot.own_detector_count == 0
    ):
        return False, "no_detection_against_stealth"
    return True, ""


def should_start_attack(
    snapshot: BattleSnapshot,
    config: UniversalTacticalConfig = DEFAULT_CONFIG,
) -> ReadinessDecision:
    safe, block_reason = composition_safety(snapshot, config)
    if not safe:
        return ReadinessDecision(False, block_reason, False, block_reason)

    predicted = snapshot.predicted_army_advantage
    income = snapshot.income_advantage
    if config.clear_advantage_attack and predicted >= Advantage.ClearAdvantage:
        return ReadinessDecision(True, "clear_predicted_army_advantage", True)
    if (
        config.timing_window_attack
        and predicted >= Advantage.SmallAdvantage
        and income <= Advantage.Even
    ):
        return ReadinessDecision(True, "army_income_timing_window", True)
    if config.max_supply_attack and snapshot.supply_used >= config.max_supply_trigger:
        return ReadinessDecision(True, "near_max_supply", True)
    return ReadinessDecision(False, "no_attack_trigger", True)
