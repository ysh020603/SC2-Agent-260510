"""Universal DEFEND/GATHER/ATTACK decision layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .battle_snapshot import BattleSnapshot
from .config import DEFAULT_CONFIG, UniversalTacticalConfig
from .posture import TacticalPosture
from .readiness import ReadinessDecision, should_start_attack


@dataclass(frozen=True)
class PostureDecision:
    posture: TacticalPosture
    reason: str
    readiness: Optional[ReadinessDecision] = None


class UniversalTacticalController:
    """State-driven controller with no skill/opening/ablation inputs."""

    def __init__(self, config: UniversalTacticalConfig = DEFAULT_CONFIG):
        self.config = config
        self.last_decision: Optional[PostureDecision] = None
        self.last_change_time: Optional[float] = None
        self.last_retreat_time: Optional[float] = None

    def note_retreat(self, game_time: float):
        self.last_retreat_time = float(game_time)
        self._accept(PostureDecision(TacticalPosture.RETREAT, "local_retreat_state"), game_time)

    def decide_posture(self, snapshot: BattleSnapshot) -> TacticalPosture:
        return self.decide(snapshot).posture

    def decide(self, snapshot: BattleSnapshot) -> PostureDecision:
        now = snapshot.game_time
        if snapshot.threatened_zone_count > 0:
            return self._accept(PostureDecision(TacticalPosture.DEFEND, "owned_zone_threatened"), now)
        if snapshot.own_total_power < self.config.global_min_attack_power:
            return self._gather("below_global_min_attack_power", now)
        if snapshot.largest_army_group_fraction < self.config.min_cohesion_to_attack:
            return self._gather("army_not_cohesive", now)
        readiness = should_start_attack(snapshot, self.config)
        if not readiness.composition_safe:
            return self._gather(readiness.reason, now, readiness)
        if (
            self.last_retreat_time is not None
            and now - self.last_retreat_time < self.config.reattack_cooldown_after_retreat
        ):
            return self._gather("reattack_cooldown", now, readiness, force=True)
        if readiness.should_attack:
            candidate = PostureDecision(TacticalPosture.ATTACK, readiness.reason, readiness)
            if self._gather_commit_active(now):
                return self.last_decision
            return self._accept(candidate, now)
        if self._attack_commit_active(now):
            return self.last_decision
        return self._gather(readiness.reason, now, readiness)

    def _gather(self, reason, now, readiness=None, force=False):
        if not force and self._attack_commit_active(now):
            return self.last_decision
        return self._accept(PostureDecision(TacticalPosture.GATHER, reason, readiness), now)

    def _attack_commit_active(self, now):
        return bool(
            self.last_decision
            and self.last_decision.posture == TacticalPosture.ATTACK
            and self.last_change_time is not None
            and now - self.last_change_time < self.config.min_attack_commit_seconds
        )

    def _gather_commit_active(self, now):
        return bool(
            self.last_decision
            and self.last_decision.posture == TacticalPosture.GATHER
            and self.last_change_time is not None
            and now - self.last_change_time < self.config.min_gather_commit_seconds
        )

    def _accept(self, decision, now):
        if self.last_decision is None or self.last_decision.posture != decision.posture:
            self.last_change_time = float(now)
        self.last_decision = decision
        return decision
