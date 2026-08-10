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
        "AI iteration timed out: 180\nSC2 client process exited: returncode=-15\n"
        "SC2_PROCESS_DISAPPEARED after launch",
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


def test_runner_pins_pending_observation_cleanup_controls():
    source = (ROOT / "tools/run_human_skill_ablation_suite.py").read_text(encoding="utf-8")
    assert '"--protocol-observation-timeout"' in source
    assert "default=120.0" in source
    assert '"SC2_PROTOCOL_OBSERVATION_TIMEOUT_SECONDS"' in source
    assert '"--protocol-drain-timeout"' in source
    assert '"SC2_PROTOCOL_DRAIN_TIMEOUT_SECONDS"' in source
    assert '"protocol_observation_timeout"' in source
    assert '"protocol_drain_timeout"' in source


def test_runtime_never_infers_result_after_transport_failure():
    source = (ROOT / "python-sc2/sc2/main.py").read_text(encoding="utf-8")
    assert "no_engine_reported_result" in source
    assert "_sc2_transport_failure" in source
    assert "last_state_surviving_force" not in source
    assert "last_state_no_own_assets" not in source
    assert "recover_from_protocol_timeout" not in source


def test_runner_uses_reference_natural_child_lifecycle():
    source = (ROOT / "tools/run_human_skill_ablation_suite.py").read_text(encoding="utf-8")
    run_job = source.split("def run_job", 1)[1].split("pending =", 1)[0]
    assert "completed_process = subprocess.run(" in run_job
    assert "start_new_session=True" not in run_job
    assert "subprocess.Popen(" not in run_job
    assert "foreign_sc2_pids()" not in run_job
    assert "_terminate_process_group(" not in run_job
    assert '"timeout",' not in run_job
    assert '"launcher_mode": "natural_subprocess_run"' in source
    assert '"foreign_sc2_runtime_monitor": False' in source


def test_foreign_sc2_scan_freezes_candidates_before_process_forest(monkeypatch):
    module = _load("human_skill_suite_scan_order", "tools/run_human_skill_ablation_suite.py")
    calls = []

    def scan_sc2():
        calls.append("sc2")
        return {101, 202}

    def scan_forest(roots):
        calls.append(("forest", set(roots)))
        return {1, 2, 101}

    monkeypatch.setattr(module, "_sc2_process_pids", scan_sc2)
    monkeypatch.setattr(module, "_process_forest", scan_forest)

    monkeypatch.setattr(module, "_process_has_trusted_owner_env", lambda pid, owner: False)
    assert module._foreign_sc2_pids({1}, {2}) == [202]
    assert calls == ["sc2", ("forest", {1, 2})]


def test_foreign_sc2_accepts_shared_owner_environment(monkeypatch):
    module = _load("human_skill_suite_owner_env", "tools/run_human_skill_ablation_suite.py")
    monkeypatch.setattr(module, "_sc2_process_pids", lambda: {101, 202, 303})
    monkeypatch.setattr(module, "_process_forest", lambda roots: {101})
    monkeypatch.setattr(
        module,
        "_process_has_trusted_owner_env",
        lambda pid, owner: pid == 202 and owner == 999,
    )
    assert module._foreign_sc2_pids({1}, {2}, 999) == [303]


def test_analyzer_supports_selected_methods_and_non_full_baseline():
    module = _load("human_skill_analyzer_methods", "tools/analyze_human_skill_ablation.py")
    methods = ("positive_only", "full_v2")
    aggregate = module.aggregate([], methods)
    assert tuple(aggregate) == methods
    assert all(item["n"] == 0 for item in aggregate.values())
    comparison = module.paired([], methods, "positive_only")
    assert tuple(comparison) == ("full_v2",)
    assert comparison["full_v2"]["paired_n"] == 0
    assert module.exact_two_sided_sign_p(1, 9) == 0.021484
