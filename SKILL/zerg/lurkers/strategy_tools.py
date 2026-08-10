from sc2.ids.unit_typeid import UnitTypeId

from SKILL.zerg.common_tools import make_zerg_strategy_tools
from SC2_Agent.prompt_context import zerg_automation_profile
from sharpy.plans.require import UnitReady


AUTOMATION_PROFILE = zerg_automation_profile(
    strategy="lurkers",
    attack_threshold=45,
    attack_gate=(
        "The attack is additionally gated until at least 2 fully ready Lurkers "
        "exist; pending Lurkers do not satisfy this gate."
    ),
)


def create_strategy_tools():
    # This route pays for a dedicated Lurker transition.  A generic mid-game
    # threshold launches the Roach/Hydra shell before LurkerDenMP completes,
    # so the match ends without ever exercising or benefiting from the named
    # composition.  Gather a materially larger force for the first positional
    # push and reinforce it with the first Lurkers.
    return make_zerg_strategy_tools(
        attack_value=AUTOMATION_PROFILE.attack_threshold,
        attack_requirement=UnitReady(UnitTypeId.LURKERMP, 2),
    )
