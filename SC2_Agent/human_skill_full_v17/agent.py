from __future__ import annotations

import re

from SC2_Agent.human_skill_common.agent_base import HumanSkillAgent

from .config import AGENT_VERSION, ALLOWED_NODE_TYPES, ALLOW_GRAPH_NAVIGATION, SKILL_METHOD
from .prompt import PROCESS_CONTRACT
from .saturation import conversion_alert, parse_live_state, saturate_combat_queue


_POOL_RE = re.compile(
    r"Human-trajectory candidate pool[^:]*:\*\*\s*([^\n]+)",
    re.IGNORECASE,
)


class HumanSkillFullV17Agent(HumanSkillAgent):
    """Knowledge graph with completion-aware, feedback-verified throughput repair."""

    def __init__(self, **kwargs):
        skill = kwargs.get("skill")
        if skill is None:
            raise ValueError("full-v17 requires a loaded skill")
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
        self._failed_progress_checks = 0
        self._previous_alert_state = None
        self._repair_level = 0

    def reset_match(self) -> None:
        super().reset_match()
        self._last_policy_time = None
        self._conversion_streak = 0
        self._failed_progress_checks = 0
        self._previous_alert_state = None
        self._repair_level = 0

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
        state = parse_live_state(obs_text)
        if self._last_policy_time != game_time_seconds:
            if reason and state is not None:
                self._conversion_streak += 1
                previous = self._previous_alert_state
                if previous is not None:
                    bank_fell = state.bank <= previous.bank - 200
                    army_grew = state.army_supply >= previous.army_supply + 4
                    used_grew = state.used_supply >= previous.used_supply + 6
                    if bank_fell or army_grew or used_grew:
                        self._failed_progress_checks = max(0, self._failed_progress_checks - 1)
                    else:
                        self._failed_progress_checks = min(4, self._failed_progress_checks + 1)
                self._previous_alert_state = state
            else:
                self._conversion_streak = 0
                self._failed_progress_checks = max(0, self._failed_progress_checks - 1)
                self._previous_alert_state = None
            self._repair_level = max(self._failed_progress_checks, self._conversion_streak - 1)
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
                if self._repair_level >= 1
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
            rotation=max(0, self._repair_level),
            repair_level=max(0, self._repair_level),
        )
