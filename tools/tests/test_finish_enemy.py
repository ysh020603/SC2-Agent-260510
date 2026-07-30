import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from sc2.units import Units

from sharpy.managers.core.roles import UnitTask
from sharpy.plans.tactics.attack_expansions import PlanFinishEnemy


class PlanFinishEnemyTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_order_overrides_gather_order_for_role_idle_army(self):
        unit = MagicMock()
        unit.type_id = UnitTypeId.ROACH

        ai = SimpleNamespace()
        ai.units = SimpleNamespace(idle=Units([], ai))

        act = PlanFinishEnemy()
        act.ai = ai
        act.roles = SimpleNamespace(
            idle=[unit],
            set_task=MagicMock(),
            all_from_task=MagicMock(return_value=[]),
            refresh_tasks=MagicMock(),
        )
        act.unit_values = SimpleNamespace(should_attack=lambda candidate: candidate is unit)
        act.find_attack_position = AsyncMock(return_value=Point2((10, 20)))

        await act.execute()

        unit.attack.assert_called_once_with(Point2((10, 20)))
        act.roles.set_task.assert_called_once_with(UnitTask.Attacking, unit)


if __name__ == "__main__":
    unittest.main()
