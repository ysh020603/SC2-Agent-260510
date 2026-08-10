from __future__ import annotations

import inspect

import run_vs_ai
import tools.run_experiment as run_experiment
from dummies.generic.universal_llm_bot import (
    NAIVE_DECISION_AGENT_MODE,
    PLAN_EXECUTE_DECISION_AGENT_MODE,
    SELF_REFINE_DECISION_AGENT_MODE,
    SUPPORTED_DECISION_AGENT_MODES,
    UniversalLLMBot,
)
from tools.experiment_config import DECISION_AGENT_MODES


def test_structural_modes_registered():
    assert PLAN_EXECUTE_DECISION_AGENT_MODE == "plan-execute"
    assert SELF_REFINE_DECISION_AGENT_MODE == "self-refine"
    assert PLAN_EXECUTE_DECISION_AGENT_MODE in SUPPORTED_DECISION_AGENT_MODES
    assert SELF_REFINE_DECISION_AGENT_MODE in SUPPORTED_DECISION_AGENT_MODES
    assert PLAN_EXECUTE_DECISION_AGENT_MODE in DECISION_AGENT_MODES
    assert SELF_REFINE_DECISION_AGENT_MODE in DECISION_AGENT_MODES


def test_defaults_unchanged():
    assert run_vs_ai.DEFAULT_DECISION_AGENT_MODE == "data-v2.2"
    bot = UniversalLLMBot(race_name="terran")
    assert bot.decision_agent_mode == "data-v2.2"
    assert NAIVE_DECISION_AGENT_MODE == "naive"


def test_launcher_sources_list_structural_modes():
    for source in (
        inspect.getsource(run_vs_ai._parse_args),
        inspect.getsource(run_experiment._parse_args),
    ):
        assert "plan-execute" in source
        assert "self-refine" in source
        assert "naive" in source
