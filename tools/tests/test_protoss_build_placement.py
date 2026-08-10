import asyncio
from types import SimpleNamespace

from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sharpy.plans.acts import GridBuilding


class _ReadyUnits(list):
    @property
    def ready(self):
        return self


class _NoStructures:
    def closer_than(self, _distance, _point):
        return _EmptyNearby()


class _EmptyNearby:
    exists = False

    def __bool__(self):
        return False


def test_protoss_placement_expands_beyond_static_solver_slots():
    pylon = SimpleNamespace(tag=7, position=Point2((30, 30)))
    dynamic_position = Point2((35.5, 30.5))
    act = GridBuilding(UnitTypeId.GATEWAY)
    act.allow_wall = True
    act.building_solver = SimpleNamespace(
        buildings2x2=[],
        buildings3x3=[],
        wall3x3=[],
    )
    act.cache = SimpleNamespace(
        own=lambda unit_type: (
            _ReadyUnits([pylon])
            if unit_type == UnitTypeId.PYLON
            else _ReadyUnits()
        )
    )

    async def find_placement(
        unit_type,
        near,
        max_distance,
        random_alternative,
        placement_step,
    ):
        assert unit_type == UnitTypeId.GATEWAY
        assert near == pylon.position
        assert max_distance == 7
        assert random_alternative is False
        assert placement_step == 1
        return dynamic_position

    act.ai = SimpleNamespace(
        structures=[],
        state=SimpleNamespace(
            psionic_matrix=SimpleNamespace(covers=lambda _point: True)
        ),
        townhalls=SimpleNamespace(ready=[]),
        find_placement=find_placement,
        workers=[],
    )

    position = asyncio.run(act.position_protoss(8))
    assert position == dynamic_position


def test_grid_building_reserves_cross_type_footprints_within_frame():
    ai = SimpleNamespace(
        state=SimpleNamespace(game_loop=200),
        time=10.0,
    )
    lurker_den = GridBuilding(UnitTypeId.LURKERDENMP)
    evolution = GridBuilding(UnitTypeId.EVOLUTIONCHAMBER)
    lurker_den.ai = ai
    evolution.ai = ai
    point = Point2((40.5, 116.5))

    lurker_den._reserve_position_this_frame(point)
    assert evolution._position_reserved_this_frame(point)
    assert evolution._position_reserved_this_frame(Point2((42.5, 116.5)))
    assert not evolution._position_reserved_this_frame(Point2((44.5, 116.5)))

    ai.state.game_loop = 201
    assert not evolution._position_reserved_this_frame(point)


def test_zerg_placement_requires_engine_can_place_confirmation():
    blocked = Point2((20.5, 20.5))
    valid = Point2((24.5, 20.5))
    calls = []

    async def can_place(unit_type, point):
        calls.append((unit_type, point))
        return point == valid

    act = GridBuilding(UnitTypeId.LURKERDENMP)
    act.building_solver = SimpleNamespace(buildings3x3=[blocked, valid])
    act.ai = SimpleNamespace(
        structures=_NoStructures(),
        state=SimpleNamespace(
            game_loop=10,
            creep=SimpleNamespace(is_set=lambda _point: True),
        ),
        can_place_single=can_place,
    )

    assert asyncio.run(act.position_zerg(0)) == valid
    assert calls == [
        (UnitTypeId.LURKERDENMP, blocked),
        (UnitTypeId.LURKERDENMP, valid),
    ]


def test_zerg_placement_expands_beyond_static_solver_slots():
    anchor = SimpleNamespace(tag=9, position=Point2((50.5, 50.5)))
    dynamic = Point2((56.5, 50.5))

    async def can_place(_unit_type, point):
        return point == dynamic

    async def find_placement(
        unit_type,
        near,
        max_distance,
        random_alternative,
        placement_step,
    ):
        assert unit_type == UnitTypeId.HYDRALISKDEN
        assert near == anchor.position
        assert max_distance == 14
        assert not random_alternative
        assert placement_step == 1
        return dynamic

    act = GridBuilding(UnitTypeId.HYDRALISKDEN)
    act.building_solver = SimpleNamespace(buildings3x3=[])
    act.ai = SimpleNamespace(
        structures=_NoStructures(),
        townhalls=SimpleNamespace(ready=[anchor]),
        state=SimpleNamespace(
            game_loop=11,
            creep=SimpleNamespace(is_set=lambda _point: True),
        ),
        can_place_single=can_place,
        find_placement=find_placement,
    )

    assert asyncio.run(act.position_zerg(0)) == dynamic
