from SC2_Agent.human_skill_common.agent_base import HumanSkillAgent
from .config import AGENT_VERSION, ALLOWED_NODE_TYPES, ALLOW_GRAPH_NAVIGATION, SKILL_METHOD
from .prompt import VARIANT_CONTRACT


class HumanSkillFrequencyOnlyAgent(HumanSkillAgent):
    def __init__(self, **kwargs):
        super().__init__(
            agent_version=AGENT_VERSION,
            skill_method=SKILL_METHOD,
            allowed_node_types=ALLOWED_NODE_TYPES,
            allow_graph_navigation=ALLOW_GRAPH_NAVIGATION,
            variant_contract=VARIANT_CONTRACT,
            **kwargs
        )
