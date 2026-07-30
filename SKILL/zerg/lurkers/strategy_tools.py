from sc2.ids.unit_typeid import UnitTypeId

from SKILL.zerg.common_tools import make_zerg_strategy_tools
from sharpy.plans.require import UnitReady


def create_strategy_tools():
    # This route pays for a dedicated Lurker transition.  A generic mid-game
    # threshold launches the Roach/Hydra shell before LurkerDenMP completes,
    # so the match ends without ever exercising or benefiting from the named
    # composition.  Gather a materially larger force for the first positional
    # push and reinforce it with the first Lurkers.
    return make_zerg_strategy_tools(
        attack_value=45,
        attack_requirement=UnitReady(UnitTypeId.LURKERMP, 2),
    )
