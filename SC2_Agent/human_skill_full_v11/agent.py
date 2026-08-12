from SC2_Agent.human_skill_common.agent_base import HumanSkillAgent

from .config import AGENT_VERSION, ALLOWED_NODE_TYPES, ALLOW_GRAPH_NAVIGATION, SKILL_METHOD
from .normalize import normalize_early_queue
from .prompt import contract_for_skill


class HumanSkillFullV11Agent(HumanSkillAgent):
    def __init__(self, **kwargs):
        skill = kwargs.get("skill")
        if skill is None:
            raise ValueError("full-v11 requires a loaded skill")
        super().__init__(agent_version=AGENT_VERSION, skill_method=SKILL_METHOD,
                         allowed_node_types=ALLOWED_NODE_TYPES,
                         allow_graph_navigation=ALLOW_GRAPH_NAVIGATION,
                         variant_contract=contract_for_skill(skill.skill_id), **kwargs)

    def _variant_transform_ordered_names(self, *, race, obs_text, ordered_names, game_time_seconds):
        return normalize_early_queue(race=race, obs_text=obs_text, ordered_names=ordered_names,
                                     game_time_seconds=game_time_seconds)
