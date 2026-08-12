import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_full_versions_are_registered_in_game_starter_cli_choices():
    tree = ast.parse((ROOT / "bot_loader" / "game_starter.py").read_text(encoding="utf-8"))
    registered = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "human-skill-full-v2" in registered
    assert "human-skill-full-v3" in registered
    assert "human-skill-full-v4" in registered
    assert "human-skill-full-v13" in registered
    assert "human-skill-full-v14" in registered
    assert "human-skill-full-v15" in registered
    assert "human-skill-full-v16" in registered
    assert "human-skill-full-v17" in registered
    assert "human-skill-full-v18" in registered
