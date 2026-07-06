import pytest

from sc2_runtime import BUNDLED_PYTHON_SC2, ensure_bundled_python_sc2


def test_agent_loads_bundled_python_sc2() -> None:
    origin = ensure_bundled_python_sc2()
    assert origin.is_relative_to(BUNDLED_PYTHON_SC2.resolve())


def test_raven_upgrade_mapping_is_available() -> None:
    ensure_bundled_python_sc2()

    from sc2.dicts.upgrade_researched_from import UPGRADE_RESEARCHED_FROM
    from sc2.ids.unit_typeid import UnitTypeId
    from sc2.ids.upgrade_id import UpgradeId

    assert (
        UPGRADE_RESEARCHED_FROM[UpgradeId.RAVENCORVIDREACTOR]
        == UnitTypeId.STARPORTTECHLAB
    )


def test_unknown_research_building_fails_fast() -> None:
    ensure_bundled_python_sc2()

    from sc2.ids.upgrade_id import UpgradeId
    from sharpy.plans.acts.tech import _research_building_for

    with pytest.raises(RuntimeError, match="HUNTERSEEKER"):
        _research_building_for(UpgradeId.HUNTERSEEKER)
