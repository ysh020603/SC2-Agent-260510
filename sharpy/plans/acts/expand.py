from typing import TYPE_CHECKING, Optional

from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sharpy.general.zone import Zone
from sharpy.managers.core.roles import UnitTask
from sharpy.managers.core import ZoneManager, UnitRoleManager
from sharpy.interfaces import IIncomeCalculator, IGatherPointSolver
from sc2.ids.unit_typeid import UnitTypeId
from sc2.unit import Unit, UnitOrder
from .act_base import ActBase
from sharpy.sc2math import to_new_ticks
from s2clientprotocol import common_pb2 as common_pb

if TYPE_CHECKING:
    from sharpy.knowledges import *


def get_new_townhall_type(race: Race):
    if race == Race.Zerg:
        return UnitTypeId.HATCHERY
    elif race == Race.Protoss:
        return UnitTypeId.NEXUS
    elif race == Race.Terran:
        return UnitTypeId.COMMANDCENTER


train_worker_abilitites = {AbilityId.NEXUSTRAIN_PROBE, AbilityId.COMMANDCENTERTRAIN_SCV}


class Expand(ActBase):
    gather_manager: IGatherPointSolver
    zone_manager: ZoneManager
    income_calculator: IIncomeCalculator
    roles: UnitRoleManager

    def __init__(
        self,
        to_count: int,
        priority: bool = False,
        consider_worker_production: bool = True,
        priority_base_index: Optional[int] = None,
    ):
        assert isinstance(to_count, int)
        self.priority_base_index = priority_base_index
        self.to_count: int = to_count
        self.builder_tag: Optional[int] = None
        self.priority = priority
        self.consider_worker_production = consider_worker_production
        self._reserved_position = None
        self._reserved_at: Optional[float] = None
        self.issued_this_frame = False

        super().__init__()

    @property
    def townhall_type(self) -> UnitTypeId:
        return get_new_townhall_type(self.knowledge.my_race)

    @property
    def current_active_base_count(self) -> int:
        count = 0

        count += len(self.zone_manager.our_zones_with_minerals)

        return count

    async def start(self, knowledge: "Knowledge"):
        await super().start(knowledge)
        self.gather_manager = knowledge.get_required_manager(IGatherPointSolver)
        self.zone_manager = knowledge.get_required_manager(ZoneManager)
        self.income_calculator = knowledge.get_required_manager(IIncomeCalculator)
        self.roles = knowledge.get_required_manager(UnitRoleManager)

    async def execute(self) -> bool:
        self.issued_this_frame = False
        if self._own_reservation_pending():
            return False
        expand_here: Optional["Zone"] = None
        zone_currently_expanding: Optional["Zone"] = None
        expand_now = False
        active_bases = self.current_active_base_count
        zones = self.zone_manager.expansion_zones

        if self.priority_base_index is not None:
            zones = sorted(zones, key=lambda z: z.zone_index == self.priority_base_index, reverse=True)

        for zone in zones:  # type: "Zone"
            if self._expansion_position_reserved(zone.center_location):
                continue
            expanding = self.expanding_in(zone)
            if expand_here is None and zone.should_expand_here:
                if not expanding:
                    expand_here = zone
                    expand_now = zone.safe_expand_here
            if expanding:
                zone_currently_expanding = zone

        if active_bases >= self.to_count:
            # We have expanded enough
            self.clear_worker()
            return True

        if expand_here is None or not self.ai.workers.exists:
            # Cannot expand
            self.clear_worker()
            return False

        worker = self.get_worker_builder(expand_here.center_location, self.builder_tag)
        pending_count = self.pending_build(self.townhall_type)

        if worker is None:
            return False

        # Inform our logic that we're looking to expand
        if zone_currently_expanding:
            self.gather_manager.set_expanding_to(zone_currently_expanding.center_location)
        else:
            self.gather_manager.set_expanding_to(expand_here.center_location)

        if pending_count:
            if self.has_build_order(worker):
                self.set_worker(worker)
            else:
                self.clear_worker()

            if active_bases + pending_count >= self.to_count:
                return True

        if expand_now:
            if self.ai.can_afford(self.townhall_type):
                if await self.build_expansion(expand_here):
                    return False
            else:
                self.possibly_move_worker(expand_here)

            cost = self.ai.calculate_cost(self.townhall_type)
            self.knowledge.reserve(cost.minerals, cost.vespene)

        return False

    def possibly_move_worker(self, zone: Zone):
        if not self.priority:
            return
        position = zone.center_location
        worker = self.get_worker_builder(position, self.builder_tag)
        if worker is None:
            return

        d = worker.distance_to(position)
        time = d / to_new_ticks(worker.movement_speed)
        available_minerals = self.ai.minerals - self.knowledge.reserved_minerals

        unit = self.ai._game_data.units[self.townhall_type.value]
        cost = self.ai._game_data.calculate_ability_cost(unit.creation_ability)

        if self.income_calculator.mineral_income > 0 and self.consider_worker_production:
            for town_hall in self.ai.townhalls:  # type: Unit
                # TODO: Zerg(?)
                if town_hall.orders:
                    starting_next_worker_in = -50 / self.income_calculator.mineral_income
                    for order in town_hall.orders:  # type: UnitOrder
                        if order.ability.id in train_worker_abilitites:
                            starting_next_worker_in += 12 * (1 - order.progress)

                    if starting_next_worker_in < time:
                        available_minerals -= 50  # should start producing workers soon now
                else:
                    available_minerals -= 50  # should start producing workers soon now

        if available_minerals + time * self.income_calculator.mineral_income >= cost.minerals:
            # Go wait
            self.set_worker(worker)

            worker.move(position)

    def set_worker(self, worker: Optional[Unit]) -> bool:
        if worker:
            self.roles.set_task(UnitTask.Building, worker)
            self.builder_tag = worker.tag
            return True

        self.builder_tag = None
        return False

    def clear_worker(self):
        if self.builder_tag is not None:
            self.roles.clear_task(self.builder_tag)
            self.builder_tag = None

    async def build_expansion(self, expand_here: "Zone") -> bool:
        worker = self.get_worker_builder(expand_here.center_location, self.builder_tag)

        if worker is not None:
            self.print(f"Expanding to {expand_here.center_location}")
            self._reserve_expansion_position(expand_here.center_location)
            worker.build(self.townhall_type, expand_here.center_location)
            self.issued_this_frame = True
            return True
        return False

    @staticmethod
    def _reservation_key(position) -> tuple[float, float]:
        return (round(float(position.x), 2), round(float(position.y), 2))

    def _live_expansion_reservations(self) -> dict:
        now = float(getattr(self.ai, "time", 0.0))
        reservations = getattr(self.ai, "_sharpy_expansion_reservations", None)
        if reservations is None:
            reservations = {}
            self.ai._sharpy_expansion_reservations = reservations
        for key, issue_time in list(reservations.items()):
            if now - float(issue_time) > 2.0:
                reservations.pop(key, None)
        return reservations

    def _expansion_position_reserved(self, position) -> bool:
        return self._reservation_key(position) in self._live_expansion_reservations()

    def _reserve_expansion_position(self, position) -> None:
        now = float(getattr(self.ai, "time", 0.0))
        key = self._reservation_key(position)
        self._live_expansion_reservations()[key] = now
        self._reserved_position = position
        self._reserved_at = now

    def _own_reservation_pending(self) -> bool:
        if self._reserved_position is None or self._reserved_at is None:
            return False
        now = float(getattr(self.ai, "time", 0.0))
        if now - float(self._reserved_at) <= 2.0:
            return True
        key = self._reservation_key(self._reserved_position)
        reservations = self._live_expansion_reservations()
        if reservations.get(key) == self._reserved_at:
            reservations.pop(key, None)
        self._reserved_position = None
        self._reserved_at = None
        return False

    async def debug_actions(self):
        if self.builder_tag is not None:
            worker: Unit = self.cache.by_tag(self.builder_tag)

            if worker and worker.orders:
                moving_status = ""
                for order in worker.orders:
                    if moving_status != "":
                        moving_status += ", "
                    moving_status += order.ability.id.name
                self.client.debug_text_world(moving_status, worker.position3d)

    def expanding_in(self, zone: "Zone") -> bool:
        """Are we already expanding to this location?"""
        creation_ability: AbilityId = self.ai._game_data.units[self.townhall_type.value].creation_ability
        for worker in self.ai.workers:
            for order in worker.orders:
                if order.ability.id == creation_ability.id:
                    if isinstance(order.target, common_pb.Point) and (order.target.x, order.target.y) == (
                        zone.center_location.x,
                        zone.center_location.y,
                    ):
                        return True

        return False
