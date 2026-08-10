"""``PlannedAction`` — one command-style action tracked by the scheduler.

The lifecycle states below describe a PA's per-frame status. ``WAITING`` is
*only* held by the action stored in :attr:`ExecutionScheduler.waiter`, which
is an independent slot from the :attr:`ExecutionScheduler.actions` list.
PAs inside ``self.actions`` are guaranteed to never carry the ``WAITING``
state (the scheduler invariants enforce this).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sc2.ids.ability_id import AbilityId

from SC2_Agent.data_tools import cost_for_action
from SC2_Agent.execution import mapping

# --- action lifecycle states ---
PENDING = "PENDING"          # not yet started this cycle, lives in scheduler.actions
WAITING = "WAITING"          # blocked on tech-chain, producer, minerals/gas, or supply (held in scheduler.waiter slot)
RUNNING = "RUNNING"          # issued, in progress (build/research act running)
DONE = "DONE"                # finished / enough issued
ABANDONED = "ABANDONED"      # waited too long, given up


@dataclass
class PlannedAction:
    action_name: str
    category: str
    canonical_name: str = ""
    queue_id: int = 0
    queue_position: int = 0
    quantity: int = 1
    ability: Optional[AbilityId] = None
    target_result: Optional[str] = None
    cost_minerals: int = 0
    cost_gas: int = 0
    cost_supply: float = 0.0
    cost_time_frames: float = 0.0
    execution_mode: str = ""
    alternative_action_names: tuple[str, ...] = ()
    output_count: int = 1

    issued_count: int = 0
    state: str = PENDING
    enqueue_time: float = 0.0
    wait_start_time: Optional[float] = None
    # 进入 RUNNING（已下达 build/research act，但尚未成功下单）的时刻；
    # 用于侦测「act 反复返回 False、永远 RUNNING」的卡死并超时放弃。
    running_start_time: Optional[float] = None
    note: str = ""

    # --- internal runtime handles (not serialised) ---
    _act: Any = field(default=None, repr=False)
    _act_started: bool = field(default=False, repr=False)
    _act_target_count: Optional[int] = field(default=None, repr=False)
    _direct_build_helper: Any = field(default=None, repr=False)
    _direct_build_base_count: Optional[int] = field(default=None, repr=False)
    _direct_build_target_count: Optional[int] = field(default=None, repr=False)
    _direct_build_worker_tag: Optional[int] = field(default=None, repr=False)
    _direct_build_reserved_positions: list = field(default_factory=list, repr=False)
    _direct_build_completed_positions: list = field(default_factory=list, repr=False)
    _direct_build_last_issue_time: Optional[float] = field(default=None, repr=False)
    _direct_build_attempts: int = field(default=0, repr=False)
    # 用于侦测 build act 的进度推进：每次新派出 SCV/下单成功（`actual_placements`
    # 增加），scheduler 会更新此快照并把 `running_start_time` 重置为当前时刻。
    # 这样 `_abandon_stuck_running` 不会在「多 quantity build 正在按节奏推进」时
    # 误杀仍在正常推进的 PA。
    _last_placement_progress: int = field(default=0, repr=False)
    _candidate_specs: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_action_name(
        cls,
        action_name: str,
        quantity: int = 1,
        *,
        canonical_name: str = "",
        queue_id: int = 0,
        queue_position: int = 0,
        target_result: Optional[str] = None,
        execution_mode: str = "",
        alternative_action_names: tuple[str, ...] = (),
        output_count: int = 1,
    ) -> "PlannedAction":
        info = cost_for_action(action_name)
        cost = info.get("cost") or {}
        category = mapping.category_for(action_name, execution_mode=execution_mode)
        return cls(
            action_name=action_name,
            category=category,
            canonical_name=canonical_name or (info.get("target_result") or action_name),
            queue_id=int(queue_id),
            queue_position=int(queue_position),
            quantity=max(1, int(quantity)),
            ability=mapping.ability_for(action_name),
            target_result=target_result or info.get("target_result"),
            cost_minerals=int(cost.get("minerals", 0) or 0),
            cost_gas=int(cost.get("gas", 0) or 0),
            cost_supply=float(cost.get("supply", 0) or 0),
            cost_time_frames=float(cost.get("time", 0) or 0),
            execution_mode=execution_mode,
            alternative_action_names=tuple(alternative_action_names),
            output_count=max(1, int(output_count)),
        )

    def select_action(
        self,
        action_name: str,
        *,
        target_result: Optional[str] = None,
        execution_mode: str = "",
    ) -> None:
        """Switch to another reviewed action candidate without changing queue identity."""
        info = cost_for_action(action_name)
        cost = info.get("cost") or {}
        self.action_name = action_name
        self.execution_mode = execution_mode or self.execution_mode
        self.category = mapping.category_for(
            action_name,
            execution_mode=self.execution_mode,
        )
        self.ability = mapping.ability_for(action_name)
        self.target_result = target_result or info.get("target_result") or self.canonical_name
        self.cost_minerals = int(cost.get("minerals", 0) or 0)
        self.cost_gas = int(cost.get("gas", 0) or 0)
        self.cost_supply = float(cost.get("supply", 0) or 0)
        self.cost_time_frames = float(cost.get("time", 0) or 0)

    # --- helpers ---
    def is_terminal(self) -> bool:
        return self.state in (DONE, ABANDONED)

    def is_waiting(self) -> bool:
        return self.state == WAITING

    def short_label(self) -> str:
        if self.quantity > 1:
            return f"{self.action_name} x{self.quantity} ({self.issued_count}/{self.quantity} issued)"
        return self.action_name

    def to_dict(self) -> dict:
        return {
            "action": self.action_name,
            "canonical_name": self.canonical_name,
            "queue_id": self.queue_id,
            "queue_position": self.queue_position,
            "category": self.category,
            "execution_mode": self.execution_mode,
            "alternative_actions": list(self.alternative_action_names),
            "output_count": self.output_count,
            "quantity": self.quantity,
            "issued": self.issued_count,
            "state": self.state,
            "supply_tier": self.supply_tier(),
            "cost": {
                "minerals": self.cost_minerals,
                "gas": self.cost_gas,
                "supply": self.cost_supply,
            },
            "note": self.note,
        }

    def supply_tier(self) -> int:
        """Classify the action by supply effect for diagnostics.

        The scheduler remains ordered; this value does not reorder tasks.
        ``cost.supply``:

        * ``< 0`` -> tier 0 (supply provider, e.g. SupplyDepot, CommandCenter)
        * ``== 0`` -> tier 1 (supply neutral)
        * ``> 0`` -> tier 2 (supply consumer, train/morph)
        """
        try:
            s = float(self.cost_supply or 0)
        except (TypeError, ValueError):
            s = 0.0
        if s < 0:
            return 0
        if s > 0:
            return 2
        return 1
