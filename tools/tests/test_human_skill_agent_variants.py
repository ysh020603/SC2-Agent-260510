from dataclasses import replace

import pytest

from SC2_Agent.human_skill_common.skill_loader import ReadableSkillLoader
from SC2_Agent.human_skill_common.validation import HumanSkillValidationError, require_non_reasoning_model
from SC2_Agent.human_skill_common.variants import VARIANTS, load_variant_package


def test_all_packages_are_pinned_and_load_fixture(fixture_skill_root, api_config):
    loader = ReadableSkillLoader(str(fixture_skill_root))
    assert len(VARIANTS) == 23
    for name, spec in VARIANTS.items():
        loaded_spec, package, agent_class = load_variant_package(name)
        assert loaded_spec == spec
        fixture_method = "full_signed_graph" if name in {"human-skill-full-v13", "human-skill-full-v14", "human-skill-full-v15", "human-skill-full-v16", "human-skill-full-v17", "human-skill-full-v18"} else spec.method
        skill = loader.load(
            method=fixture_method,
            race="protoss",
            matchup="PvP",
            skill_id="PvP_O01",
            allowed_node_types=package.ALLOWED_NODE_TYPES,
            allow_graph_navigation=package.ALLOW_GRAPH_NAVIGATION,
        )
        if name in {"human-skill-full-v13", "human-skill-full-v14", "human-skill-full-v15", "human-skill-full-v16", "human-skill-full-v17", "human-skill-full-v18"}:
            skill = replace(skill, method=spec.method)
        agent = agent_class(
            loader=loader,
            skill=skill,
            model_key="DeepSeek-V4-flash",
            api_config_path=str(api_config),
            llm_call=lambda *_: {},
        )
        assert agent.skill_method == spec.method


def test_reasoning_and_think_model_are_forbidden(api_config):
    require_non_reasoning_model("DeepSeek-V4-flash", str(api_config))
    with pytest.raises(HumanSkillValidationError):
        require_non_reasoning_model("DeepSeek-V4-flash_think", str(api_config))
