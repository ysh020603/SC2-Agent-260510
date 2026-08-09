import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_runner_detects_protocol_watchdog_in_match_log(tmp_path):
    module = _load("human_skill_suite", "tools/run_human_skill_ablation_suite.py")
    (tmp_path / "match.log").write_text(
        "Recovered stalled SC2 protocol request: observation", encoding="utf-8"
    )
    assert module.record_has_watchdog(tmp_path) is True


def test_runner_accepts_clean_match_log(tmp_path):
    module = _load("human_skill_suite_clean", "tools/run_human_skill_ablation_suite.py")
    (tmp_path / "match.log").write_text("Result: Victory", encoding="utf-8")
    assert module.record_has_watchdog(tmp_path) is False
