from SKILL.zerg.common_tools import make_zerg_strategy_tools
from SC2_Agent.prompt_context import zerg_automation_profile


AUTOMATION_PROFILE = zerg_automation_profile(
    strategy="roach_hydra",
    attack_threshold=28,
)


def create_strategy_tools():
    return make_zerg_strategy_tools(
        attack_value=AUTOMATION_PROFILE.attack_threshold
    )
