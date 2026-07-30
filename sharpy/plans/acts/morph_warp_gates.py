import sc2
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId
from sc2.unit import Unit
from .act_base import ActBase


class MorphWarpGates(ActBase):
    def __init__(self):
        super().__init__()

    async def execute(self) -> bool:
        if UpgradeId.WARPGATERESEARCH not in self.ai.state.upgrades:
            return True
        target: Unit
        for target in self.cache.own(UnitTypeId.GATEWAY).ready.idle:
            if target.tag in self.ai.unit_tags_received_action:
                continue
            target(AbilityId.MORPH_WARPGATE)

        return True
