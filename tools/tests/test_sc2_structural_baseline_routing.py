from __future__ import annotations

import inspect

import run_vs_ai
import tools.run_experiment as run_experiment
from dummies.generic.universal_llm_bot import (
    COS_DECISION_AGENT_MODE,
    HIMA_DECISION_AGENT_MODE,
    STRUCTURAL_BASELINE_DECISION_AGENT_MODES,
    SUNTZU_DECISION_AGENT_MODE,
    SUPPORTED_DECISION_AGENT_MODES,
    UniversalLLMBot,
)
from tools.experiment_config import DECISION_AGENT_MODES


def test_sc2_structural_modes_registered():
    for mode in ("suntzu", "hima", "cos"):
        assert mode in SUPPORTED_DECISION_AGENT_MODES
        assert mode in DECISION_AGENT_MODES
        assert mode in STRUCTURAL_BASELINE_DECISION_AGENT_MODES
    assert SUNTZU_DECISION_AGENT_MODE == "suntzu"
    assert HIMA_DECISION_AGENT_MODE == "hima"
    assert COS_DECISION_AGENT_MODE == "cos"


def test_defaults_still_data_v22():
    assert run_vs_ai.DEFAULT_DECISION_AGENT_MODE == "data-v2.2"
    assert UniversalLLMBot(race_name="terran").decision_agent_mode == "data-v2.2"


def test_launcher_sources_list_new_modes():
    for source in (
        inspect.getsource(run_vs_ai._parse_args),
        inspect.getsource(run_experiment._parse_args),
    ):
        assert "suntzu" in source
        assert "hima" in source
        assert "cos" in source
