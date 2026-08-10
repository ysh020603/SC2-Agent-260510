from SKILL.zerg.common_tools import make_zerg_strategy_tools
from SC2_Agent.prompt_context import zerg_automation_profile


AUTOMATION_PROFILE = zerg_automation_profile(
    strategy="twelve_pool",
    attack_threshold=2,
    spread_creep=False,
)


def create_strategy_tools():
    return make_zerg_strategy_tools(
        attack_value=AUTOMATION_PROFILE.attack_threshold,
        spread_creep=False,
    )
