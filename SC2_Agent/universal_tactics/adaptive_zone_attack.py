"""PlanZoneAttack with a universal state-driven start gate."""

from __future__ import annotations

from sharpy.plans.tactics import PlanZoneAttack

from .battle_snapshot import BattleSnapshotBuilder
from .config import DEFAULT_CONFIG, UniversalTacticalConfig
from .controller import UniversalTacticalController
from .logging import TacticalTraceLogger
from .posture import TacticalPosture


class AdaptiveZoneAttack(PlanZoneAttack):
    """Preserve target selection, role management, micro and local retreat."""

    def __init__(
        self,
        controller=None,
        snapshot_builder=None,
        trace_logger=None,
        config: UniversalTacticalConfig = DEFAULT_CONFIG,
    ):
        super().__init__(config.global_min_attack_power)
        self.config = config
        self.controller = controller or UniversalTacticalController(config)
        self.snapshot_builder = snapshot_builder or BattleSnapshotBuilder(config)
        self.trace_logger = trace_logger
        self._last_snapshot = None
        self._last_posture = None

    async def start(self, knowledge):
        await super().start(knowledge)
        await self.snapshot_builder.start(knowledge)
        if self.trace_logger:
            # Materialize one trace file for every started game, including
            # games that end before the first posture transition.
            self.trace_logger.flush()

    def _should_attack(self, power):
        snapshot = self.snapshot_builder.build()
        self._last_snapshot = snapshot
        decision = self.controller.decide(snapshot)
        previous = self._last_posture
        self._last_posture = decision.posture
        if self.trace_logger and previous != decision.posture:
            self.trace_logger.record(
                game_time=snapshot.game_time,
                from_posture=previous,
                to_posture=decision.posture,
                reason=decision.reason,
                snapshot=snapshot,
            )
        if self.config.debug_logging:
            self.print("Universal posture {}: {}".format(decision.posture.value, decision.reason))
        return decision.posture == TacticalPosture.ATTACK and power.power >= self.config.global_min_attack_power

    def _start_attack(self, power, attackers):
        super()._start_attack(power, attackers)
        if self.trace_logger and self._last_snapshot:
            self.trace_logger.record(
                game_time=self._last_snapshot.game_time,
                from_posture=TacticalPosture.GATHER,
                to_posture=TacticalPosture.ATTACK,
                reason=(self.controller.last_decision.reason if self.controller.last_decision else "attack_ready"),
                snapshot=self._last_snapshot,
                event="attack_start",
            )

    def _start_retreat(self, status):
        super()._start_retreat(status)
        game_time = float(self.ai.time)
        self._last_snapshot = self.snapshot_builder.build()
        self.controller.note_retreat(game_time)
        if self.trace_logger:
            self.trace_logger.record(
                game_time=game_time,
                from_posture=TacticalPosture.ATTACK,
                to_posture=TacticalPosture.RETREAT,
                reason="local_combat_power_retreat",
                snapshot=self._last_snapshot,
                event="retreat_start",
            )
