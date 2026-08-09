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


def test_runner_rejects_ai_iteration_and_client_exit_markers(tmp_path):
    module = _load("human_skill_suite_runtime_markers", "tools/run_human_skill_ablation_suite.py")
    (tmp_path / "match.log").write_text(
        "AI iteration timed out: 180\nSC2 client process exited: returncode=-15",
        encoding="utf-8",
    )
    assert module.record_has_watchdog(tmp_path) is True


def test_runner_exposes_all_readable_skill_methods():
    module = _load("human_skill_suite_methods", "tools/run_human_skill_ablation_suite.py")
    assert set(module.METHODS) == {
        "full",
        "full_v2",
        "single_trace",
        "static_population",
        "flat_adaptive",
        "positive_only",
        "frequency_only",
    }


def test_analyzer_supports_selected_methods_and_non_full_baseline():
    module = _load("human_skill_analyzer_methods", "tools/analyze_human_skill_ablation.py")
    methods = ("positive_only", "full_v2")
    aggregate = module.aggregate([], methods)
    assert tuple(aggregate) == methods
    assert all(item["n"] == 0 for item in aggregate.values())
    comparison = module.paired([], methods, "positive_only")
    assert tuple(comparison) == ("full_v2",)
    assert comparison["full_v2"]["paired_n"] == 0
