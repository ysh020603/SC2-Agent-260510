from __future__ import annotations

import re

from SC2_Agent.human_skill_common.agent_base import HumanSkillAgent

from .config import AGENT_VERSION, ALLOWED_NODE_TYPES, ALLOW_GRAPH_NAVIGATION, SKILL_METHOD
from .prompt import PROCESS_CONTRACT
from .saturation import conversion_alert, saturate_combat_queue


_POOL_RE = re.compile(
    r"Human-trajectory candidate pool[^:]*:\*\*\s*([^\n]+)",
    re.IGNORECASE,
)


class HumanSkillFullV15Agent(HumanSkillAgent):
    """Knowledge-overlay graph with database-driven resource conversion repair."""

    def __init__(self, **kwargs):
        skill = kwargs.get("skill")
        if skill is None:
            raise ValueError("full-v15 requires a loaded skill")
        super().__init__(
            agent_version=AGENT_VERSION,
            skill_method=SKILL_METHOD,
            allowed_node_types=ALLOWED_NODE_TYPES,
            allow_graph_navigation=ALLOW_GRAPH_NAVIGATION,
            variant_contract=PROCESS_CONTRACT,
            **kwargs,
        )
        self._last_policy_time: float | None = None
        self._conversion_streak = 0

    def reset_match(self) -> None:
        super().reset_match()
        self._last_policy_time = None
        self._conversion_streak = 0

    def _candidate_pool(self) -> list[str]:
        names: list[str] = []
        for content in self.memory.visited_node_contents.values():
            for match in _POOL_RE.finditer(content):
                for raw in match.group(1).split(","):
                    name = raw.strip().strip(".*`")
                    if name and name not in names:
                        names.append(name)
        return names

    def _runtime_policy_context(self, *, race, obs_text, game_time_seconds):
        reason = conversion_alert(obs_text, game_time_seconds)
        if self._last_policy_time != game_time_seconds:
            self._conversion_streak = self._conversion_streak + 1 if reason else 0
            self._last_policy_time = game_time_seconds
        if not reason:
            return ""
        return (
            "[General Execution Alert] Live state shows " + reason + ". The runtime will front-load "
            "a database-validated batch of currently producible combat actions and any required supply "
            "before optional economy or technology. Keep the strategic choice grounded in the current "
            "human-trajectory node and Enemy Intelligence. "
            + (
                "The condition persisted: choose a different reachable candidate or bottleneck repair "
                "instead of repeating the previous posture."
                if self._conversion_streak >= 2
                else "Recheck spending, active production, and army growth at the next decision."
            )
        )

    def _variant_transform_ordered_names(self, *, race, obs_text, ordered_names, game_time_seconds):
        return saturate_combat_queue(
            race=race,
            obs_text=obs_text,
            ordered_names=ordered_names,
            knowledge_candidates=self._candidate_pool(),
            game_time_seconds=game_time_seconds,
            rotation=max(0, self._conversion_streak - 1),
        )
