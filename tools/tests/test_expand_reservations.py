from types import SimpleNamespace

from sc2.position import Point2

from sharpy.plans.acts import Expand


def test_expansion_reservation_is_shared_during_confirmation_window():
    ai = SimpleNamespace(time=10.0)
    first = Expand(2)
    second = Expand(3)
    first.ai = ai
    second.ai = ai
    position = Point2((70.5, 117.5))

    first._reserve_expansion_position(position)
    assert first._own_reservation_pending()
    assert second._expansion_position_reserved(position)

    ai.time = 12.1
    assert not first._own_reservation_pending()
    assert not second._expansion_position_reserved(position)
