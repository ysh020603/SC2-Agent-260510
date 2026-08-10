import json

import pytest

from SC2_Agent.human_skill_common.skill_loader import ReadableSkillLoader
from SC2_Agent.human_skill_common.validation import HumanSkillValidationError


def test_root_and_node_load(fixture_skill_root):
    loader = ReadableSkillLoader(str(fixture_skill_root))
    skill = loader.load(
        method="full_signed_graph",
        race="protoss",
        matchup="PvP",
        skill_id="PvP_O01",
        allowed_node_types={"positive", "negative", "default"},
        allow_graph_navigation=True,
    )
    assert skill.root_markdown.startswith("# Cyber Core Expand")
    assert "Recommended Strategic Direction" in loader.read_node(skill, "N001")


def test_invalid_node_and_path_traversal_rejected(fixture_skill_root, tmp_path):
    loader = ReadableSkillLoader(str(fixture_skill_root))
    skill = loader.load(
        method="full_signed_graph",
        race="protoss",
        matchup="PvP",
        skill_id="PvP_O01",
        allowed_node_types={"positive", "negative", "default"},
        allow_graph_navigation=True,
    )
    with pytest.raises(HumanSkillValidationError):
        loader.read_node(skill, "../provenance/method_ir.json")
    with pytest.raises(HumanSkillValidationError):
        loader.load(
            method="full_signed_graph",
            race="protoss",
            matchup="PvP",
            skill_id="../x",
            allowed_node_types={"positive"},
            allow_graph_navigation=True,
        )


def test_flat_agent_rejects_graph_children(fixture_skill_root, tmp_path):
    source = fixture_skill_root / "ablation_flat_adaptive" / "protoss" / "PvP" / "PvP_O01"
    target = tmp_path / "ablation_flat_adaptive" / "protoss" / "PvP" / "PvP_O01"
    target.mkdir(parents=True)
    (target / "nodes").mkdir()
    (target / "SKILL.md").write_text((source / "SKILL.md").read_text(), encoding="utf-8")
    (target / "nodes" / "N001.md").write_text((source / "nodes" / "N001.md").read_text(), encoding="utf-8")
    index = json.loads((source / "index.json").read_text())
    index["nodes"]["N001"]["children"] = ["N001"]
    (target / "index.json").write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(HumanSkillValidationError, match="graph navigation"):
        ReadableSkillLoader(str(tmp_path)).load(
            method="ablation_flat_adaptive",
            race="protoss",
            matchup="PvP",
            skill_id="PvP_O01",
            allowed_node_types={"positive", "negative", "default"},
            allow_graph_navigation=False,
        )
