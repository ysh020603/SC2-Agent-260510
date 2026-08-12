import json
from pathlib import Path

from tools.build_knowledge_executable_full_v14 import (
    KNOWLEDGE_METHOD,
    OUTPUT_METHOD,
    POLICY_METHOD,
    align_nodes,
    build,
    merge_node,
)


def test_alignment_prefers_semantically_matching_state():
    policy = {
        "P1": {"title": "Ground defense", "summary": "defend ground pressure with army"},
        "P2": {"title": "Air transition", "summary": "enemy flying units require anti air"},
    }
    knowledge = {
        "K1": {"title": "Air response", "summary": "respond to enemy flying air units"},
        "K2": {"title": "Ground pressure", "summary": "hold ground attack with defenders"},
    }
    mapping = align_nodes(policy, knowledge)
    assert mapping["P1"][0] == "K2"
    assert mapping["P2"][0] == "K1"


def test_merge_preserves_policy_and_adds_only_constraint_overlay():
    policy = "# Node\n\n## Recommended Strategic Direction\n\nKeep producing.\n\n## Possible Next Situations\n\nNext.\n"
    knowledge = "# Knowledge\n\n## Applicability Checks\n\n- Check a prerequisite.\n\n## Knowledge-Grounded Execution Envelope\n\n**Human-trajectory candidate pool (not an ordered build list):** UnitA\n"
    merged = merge_node(policy, knowledge, "K1", 0.75)
    assert "Keep producing." in merged
    assert "Knowledge Constraint Overlay" in merged
    assert "candidate pool" in merged
    assert merged.index("Knowledge Constraint Overlay") < merged.index("Possible Next Situations")


def _write_skill(root: Path, method: str, node_text: str):
    directory = root / method / "protoss" / "PvP" / "PvP_O01"
    (directory / "nodes").mkdir(parents=True)
    index = {
        "skill_id": "PvP_O01",
        "method": method,
        "root": "SKILL.md",
        "nodes": {
            "N001": {
                "path": "nodes/N001.md", "type": "default", "children": [],
                "title": "Ground macro", "summary": "ground macro army", "trigger_summary": "ground pressure",
            }
        },
    }
    (directory / "index.json").write_text(json.dumps(index), encoding="utf-8")
    (directory / "SKILL.md").write_text("# Skill\n\n- Method: old\n", encoding="utf-8")
    (directory / "nodes" / "N001.md").write_text(node_text, encoding="utf-8")


def _add_negative(root: Path):
    directory = root / KNOWLEDGE_METHOD / "protoss" / "PvP" / "PvP_O01"
    index_path = directory / "index.json"
    index = json.loads(index_path.read_text())
    index["nodes"]["N002"] = {
        "path": "nodes/N002.md", "type": "negative", "children": [],
        "title": "Failed ground greed", "summary": "ground greed failure", "trigger_summary": "bank not spent",
    }
    index_path.write_text(json.dumps(index), encoding="utf-8")
    (directory / "nodes" / "N002.md").write_text(
        "# N002 — Failure\n\n## General Failure Mode\n\nBank not spent.\n\n## Risk Direction\n\nAvoid greed.\n\n## Possible Next Situations\n\nDo not copy.\n",
        encoding="utf-8",
    )


def test_build_uses_runtime_root_and_preserves_policy_identity(tmp_path: Path):
    _write_skill(tmp_path, POLICY_METHOD, "# Policy\n\n## Recommended Strategic Direction\n\nExecutable policy.\n")
    _write_skill(
        tmp_path,
        KNOWLEDGE_METHOD,
        "# Knowledge\n\n## Applicability Checks\n\n- Factual check.\n\n## Knowledge-Grounded Execution Envelope\n\n**Human-trajectory candidate pool (not an ordered build list):** UnitA\n",
    )
    _add_negative(tmp_path)
    manifest = build(tmp_path)
    target = tmp_path / OUTPUT_METHOD / "protoss" / "PvP" / "PvP_O01"
    assert manifest["skills"] == 1
    assert json.loads((target / "index.json").read_text())["method"] == OUTPUT_METHOD
    assert "Executable policy." in (target / "nodes" / "N001.md").read_text()
    assert "Factual check." in (target / "nodes" / "N001.md").read_text()
    output_index = json.loads((target / "index.json").read_text())
    assert output_index["nodes"]["KNEG001"]["type"] == "negative"
    assert "KNEG001" in output_index["nodes"]["N001"]["children"]
    assert "Possible Next Situations" not in (target / "nodes" / "KNEG001.md").read_text()
