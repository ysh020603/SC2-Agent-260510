import os
from typing import Dict, List, Optional, Set

from sharpy.managers.core.manager_base import ManagerBase
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.ability_id import AbilityId
from sc2.unit import Unit
from sc2.units import Units
from sc2.protocol import (
    ConnectionAlreadyClosedError,
    ProtocolResponseTimeoutError,
    SC2ProcessExitedError,
)


def _available_abilities_refresh_due(
    *, current_game_loop: int, last_refresh_game_loop: int, interval_game_loops: int
) -> bool:
    return current_game_loop - last_refresh_game_loop >= max(1, interval_game_loops)


class CooldownManager(ManagerBase):
    """
    Global cooldown manager that is shared between all units.
    TODO: Rename to ability manager?
    """

    def __init__(self):
        super().__init__()
        self.used_dict: Dict[int, Dict[AbilityId, float]] = dict()
        self.available_dict: Dict[int, List[AbilityId]] = dict()
        self.adept_to_shade: Dict[int, int] = dict()
        self.shade_to_adept: Dict[int, int] = dict()
        self._shade_tags_handled: Set[int] = set()
        self._last_available_refresh_game_loop = -1_000_000

    async def update(self):
        if len(self.ai.all_own_units) < 1:
            return
        try:
            refresh_interval = max(
                1,
                int(os.environ.get("SC2_AVAILABLE_ABILITIES_REFRESH_GAME_LOOPS", "44")),
            )
        except (TypeError, ValueError):
            refresh_interval = 44
        current_game_loop = int(getattr(self.ai.state, "game_loop", 0))
        if not _available_abilities_refresh_due(
            current_game_loop=current_game_loop,
            last_refresh_game_loop=self._last_available_refresh_game_loop,
            interval_game_loops=refresh_interval,
        ):
            return
        self._last_available_refresh_game_loop = current_game_loop

        try:
            chunk_size = max(
                1,
                int(os.environ.get("SC2_AVAILABLE_ABILITIES_QUERY_CHUNK_SIZE", "32")),
            )
        except (TypeError, ValueError):
            chunk_size = 32
        units = list(self.ai.all_own_units)
        try:
            result: List[List[AbilityId]] = []
            for start in range(0, len(units), chunk_size):
                result.extend(
                    await self.ai.get_available_abilities(units[start : start + chunk_size])
                )
        except (
            ConnectionAlreadyClosedError,
            ProtocolResponseTimeoutError,
            SC2ProcessExitedError,
        ):
            # These are match-terminal transport failures. Swallowing them here
            # makes the bot issue the same doomed query every frame and can grow
            # a single log into gigabytes after the native client has exited.
            raise
        except Exception as e:
            self.print(f"Get available abilities failed: {e}")
            return

        self.available_dict.clear()
        for unit, abilities in zip(units, result):
            self.available_dict[unit.tag] = abilities

        shades = self.cache.own(UnitTypeId.ADEPTPHASESHIFT)

        if len(shades) == 0:
            self.adept_to_shade.clear()
            self.shade_to_adept.clear()
            self._shade_tags_handled.clear()
        else:
            adepts: Units = self.cache.own(UnitTypeId.ADEPT)
            current_shade_tags = set()

            if adepts.exists:
                for shade in shades:  # type: Unit
                    current_shade_tags.add(shade.tag)
                    if shade.tag not in self._shade_tags_handled:
                        self._shade_tags_handled.add(shade.tag)
                        closest = adepts.closest_to(shade)
                        self.adept_to_shade[closest.tag] = shade.tag
                        self.shade_to_adept[shade.tag] = closest.tag

                tags = []
                for shade_tag in self.shade_to_adept.keys():
                    tags.append(shade_tag)

                for shade_tag in tags:
                    if shade_tag in current_shade_tags:
                        # Shade is still alive, move along
                        continue

                    # remove adept tag from dictionaries
                    adept_tag = self.shade_to_adept.get(shade_tag, None)
                    if adept_tag is not None and adept_tag in self.adept_to_shade:
                        self.adept_to_shade.pop(adept_tag)
                    self.shade_to_adept.pop(shade_tag)

    async def post_update(self):
        pass

    @property
    def time(self) -> float:
        return self.knowledge.ai.time

    def is_ready(self, unit_tag: int, ability: AbilityId, cooldown: Optional[float] = None) -> bool:
        if cooldown is None:
            return ability in self.available_dict.get(unit_tag, [])

        ability_dict = self.used_dict.get(unit_tag, None)
        if ability_dict is None:
            return True

        last_used = ability_dict.get(ability, -1000)

        return last_used + cooldown < self.time

    def used_ability(self, unit_tag: int, ability: AbilityId) -> None:
        ability_dict = self.used_dict.get(unit_tag, None)

        if ability_dict is None:
            ability_dict = {}
            self.used_dict[unit_tag] = ability_dict

        ability_dict[ability] = self.time
