from __future__ import annotations

from functools import lru_cache
import re

from SC2_Agent.data_tools import action_candidates_for_entity
from SC2_Agent.data_tools.sc2_data_common import build_entity_indexes, load_database
from SC2_Agent.human_skill_common.agent_base import HumanSkillAgent

from .config import AGENT_VERSION, ALLOWED_NODE_TYPES, ALLOW_GRAPH_NAVIGATION, SKILL_METHOD
from .prompt import contract_for_skill


@lru_cache(maxsize=1)
def _unit_index():
    units, _ = build_entity_indexes(load_database())
    return units


def _metrics(obs_text: str) -> dict[str, float]:
    resource = re.search(r"\[Economy\]\s*([0-9]+) minerals,\s*([0-9]+) vespene", obs_text, re.I)
    army = re.search(r"Supply:.*?\(workers.*?army\s*([0-9]+(?:\.[0-9]+)?)\)", obs_text, re.I)
    if not resource or not army:
        return {}
    return {"bank": float(resource.group(1)) + float(resource.group(2)), "army": float(army.group(1))}


def _combat_actions(race: str, ordered_names: list[str]) -> list[str]:
    result = []
    units = _unit_index()
    for name in ordered_names:
        try:
            candidates = action_candidates_for_entity(race, name)
        except Exception:
            candidates = []
        for candidate in candidates:
            item = units.get(candidate.target_result) or {}
            if item and not item.get("is_structure") and not item.get("is_worker") and float(item.get("supply") or 0) > 0:
                result.append(name)
                break
    return result


class HumanSkillFullV13Agent(HumanSkillAgent):
    def __init__(self, **kwargs):
        skill = kwargs.get("skill")
        if skill is None:
            raise ValueError("full-v13 requires a loaded skill")
        super().__init__(agent_version=AGENT_VERSION, skill_method=SKILL_METHOD,
                         allowed_node_types=ALLOWED_NODE_TYPES,
                         allow_graph_navigation=ALLOW_GRAPH_NAVIGATION,
                         variant_contract=contract_for_skill(skill.skill_id), **kwargs)

        self._last_policy_time = None
        self._conversion_deficit_streak = 0

    def reset_match(self) -> None:
        super().reset_match()
        self._last_policy_time = None
        self._conversion_deficit_streak = 0

    @staticmethod
    def _conversion_alert(obs_text: str, game_time_seconds: float) -> bool:
        state = _metrics(obs_text)
        if not state:
            return False
        return (
            game_time_seconds >= 300 and state["bank"] >= 750 and state["army"] < 15
        ) or (
            game_time_seconds >= 600 and state["bank"] >= 1500 and state["army"] < 30
        )

    def _runtime_policy_context(self, *, race, obs_text, game_time_seconds):
        alert = self._conversion_alert(obs_text, game_time_seconds)
        if self._last_policy_time != game_time_seconds:
            self._conversion_deficit_streak = self._conversion_deficit_streak + 1 if alert else 0
            self._last_policy_time = game_time_seconds
        if not alert:
            return ""
        repeated = self._conversion_deficit_streak >= 2
        return (
            "[Knowledge-Grounded Process Alert] The live bank/army posture matches the cross-match "
            "resource-to-army conversion failure. Select at least one currently executable combat "
            "candidate from the read node after checking supply, producers, prerequisites, and queues. "
            + (
                "The deficit persisted across decisions: do not repeat the same posture; re-read the best "
                "node and repair the concrete producer/resource/supply bottleneck."
                if repeated else
                "Recheck at the next decision whether the bank fell and army production increased."
            )
        )

    def _variant_decision_error(self, *, race, obs_text, ordered_names, game_time_seconds):
        if not self._conversion_alert(obs_text, game_time_seconds):
            return ""
        if _combat_actions(race, ordered_names):
            return ""
        return (
            "FINAL_DECISION rejected: the live state matches the cross-match resource-to-army "
            "conversion failure (large bank with low army), but the replacement queue contains no "
            "combat-unit action. Re-read the current node's knowledge-grounded candidate pool if needed, "
            "then include at least one currently executable combat candidate after any immediate supply "
            "or producer prerequisite. Do not answer with only workers, expansion, structures, or upgrades."
        )
