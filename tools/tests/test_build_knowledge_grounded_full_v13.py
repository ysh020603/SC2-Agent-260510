from pathlib import Path

from tools.build_knowledge_grounded_full_v13 import OUTPUT_METHOD, resolve_destination


def test_default_destination_matches_runtime_parent_skill_root(tmp_path: Path):
    repo_root = tmp_path / "SC2trace2nl" / "SC2-Agent-human-skill"
    expected = tmp_path / "SC2trace2nl" / "SKILL_MINING_V2_READABLE" / OUTPUT_METHOD
    assert resolve_destination(repo_root) == expected.resolve()


def test_explicit_destination_root_is_supported(tmp_path: Path):
    skill_root = tmp_path / "deployed-skills"
    assert resolve_destination(tmp_path / "agent", skill_root) == (skill_root / OUTPUT_METHOD).resolve()
