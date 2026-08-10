from SKILL.protoss.common_tools import make_protoss_strategy_tools
from SC2_Agent.prompt_context import protoss_automation_profile


AUTOMATION_PROFILE = protoss_automation_profile(
    strategy="macro_stalkers",
    attack_threshold=18,
)


def create_strategy_tools():
    return make_protoss_strategy_tools(
        attack_value=AUTOMATION_PROFILE.attack_threshold
    )
