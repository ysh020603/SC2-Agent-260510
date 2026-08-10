"""Single frozen configuration shared by every skill and ablation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class UniversalTacticalConfig:
    min_cohesion_to_attack: float = 0.72
    # Live 1200-second calibration showed that a nominal power of 6-9 can be
    # assessed as a small advantage yet is too brittle to survive the first
    # counter-attack.  Require a real army core before leaving gather posture.
    global_min_attack_power: float = 12.0

    clear_advantage_attack: bool = True
    timing_window_attack: bool = True
    max_supply_attack: bool = True
    max_supply_trigger: float = 190.0

    enemy_air_fraction_gate: float = 0.35
    min_anti_air_coverage_ratio: float = 0.80
    enemy_ground_fraction_gate: float = 0.50
    min_anti_ground_coverage_ratio: float = 0.80
    block_attack_without_detection: bool = True

    min_attack_commit_seconds: float = 15.0
    min_gather_commit_seconds: float = 8.0
    reattack_cooldown_after_retreat: float = 12.0
    cohesion_link_distance: float = 12.0
    meaningful_zone_threat_power: float = 0.5
    debug_logging: bool = False

    def as_dict(self):
        return asdict(self)

    def stable_hash(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


DEFAULT_CONFIG = UniversalTacticalConfig()
