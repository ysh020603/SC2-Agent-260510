"""Match-scoped explicit skill read memory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MatchSkillMemory:
    skill_id: str
    method: str
    visited_node_ids: List[str] = field(default_factory=list)
    visited_node_contents: Dict[str, str] = field(default_factory=dict)
    read_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def remember(
        self,
        node_id: str,
        content: str,
        *,
        node_type: str,
        game_time: float,
        decision_cycle: int,
    ) -> bool:
        first_read = node_id not in self.visited_node_contents
        if first_read:
            self.visited_node_ids.append(node_id)
            self.visited_node_contents[node_id] = content
            self.read_stats[node_id] = {
                "node_type": node_type,
                "first_read_game_time": round(float(game_time), 2),
                "reuse_count": 0,
                "decision_cycles_using_node": [],
            }
        else:
            self.read_stats[node_id]["reuse_count"] += 1
        self.mark_cycle(decision_cycle)
        return first_read

    def mark_cycle(self, decision_cycle: int) -> None:
        for node_id in self.visited_node_ids:
            cycles = self.read_stats[node_id]["decision_cycles_using_node"]
            if decision_cycle not in cycles:
                cycles.append(decision_cycle)

    def rendered_nodes(self) -> str:
        if not self.visited_node_ids:
            return "(none)"
        return "\n\n".join(
            f"===== {node_id} =====\n{self.visited_node_contents[node_id]}" for node_id in self.visited_node_ids
        )

    def reset(self, *, skill_id: str | None = None, method: str | None = None) -> None:
        if skill_id is not None:
            self.skill_id = skill_id
        if method is not None:
            self.method = method
        self.visited_node_ids.clear()
        self.visited_node_contents.clear()
        self.read_stats.clear()

    def to_log(self) -> Dict[str, Any]:
        return {
            "schema_version": 5,
            "skill_id": self.skill_id,
            "skill_method": self.method,
            "visited_node_ids": list(self.visited_node_ids),
            "nodes": self.read_stats,
        }
