import importlib.util
import json
from pathlib import Path

from sc2.ids.unit_typeid import UnitTypeId

from SC2_Agent.top_agent import parse_strategy_summary
from sharpy.plans.build_step import Step
from sharpy.plans.require import UnitReady
from sharpy.plans.tactics import PlanZoneAttack


ROOT = Path(__file__).resolve().parents[2]


def _registered_strategies(race: str) -> list[str]:
    registry_path = ROOT / "SKILL" / race / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    return registry["registered_strategies"]


def test_every_registered_strategy_has_one_summary_file():
    for race in ("terran", "protoss", "zerg"):
        strategies = _registered_strategies(race)
        assert strategies
        assert len(strategies) == len(set(strategies))
        for strategy in strategies:
            directory = ROOT / "SKILL" / race / strategy
            files = sorted(directory.glob("*.md"))
            assert [path.name for path in files] == ["Top_agent.md"]
            text = files[0].read_text(encoding="utf-8")
            assert text.lstrip().startswith("# Summary")
            assert "# Details" not in text
            assert "[Step " not in text
            assert parse_strategy_summary(text)


def test_every_registered_strategy_tools_module_imports():
    for race in ("terran", "protoss", "zerg"):
        for strategy in _registered_strategies(race):
            path = ROOT / "SKILL" / race / strategy / "strategy_tools.py"
            assert path.is_file()
            spec = importlib.util.spec_from_file_location(
                f"test_strategy_tools_{race}_{strategy}", path
            )
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            has_factory = callable(getattr(module, "create_strategy_tools", None))
            has_strategy_class = any(
                name.endswith("StrategyTools")
                for name in vars(module)
                if isinstance(getattr(module, name), type)
            )
            assert has_factory or has_strategy_class


def test_lurker_strategy_waits_for_real_lurkers_before_attacking():
    from SKILL.zerg.lurkers.strategy_tools import create_strategy_tools

    build_order = create_strategy_tools()
    tactics = build_order.orders[0].orders
    attack_step = tactics[-2]

    assert isinstance(attack_step, Step)
    assert isinstance(attack_step.requirement, UnitReady)
    assert attack_step.requirement.unit_type == UnitTypeId.LURKERMP
    assert attack_step.requirement.count == 2
    assert isinstance(attack_step.action, PlanZoneAttack)
