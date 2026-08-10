import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_full_v2_is_registered_in_game_starter_cli_choices():
    tree = ast.parse((ROOT / "bot_loader" / "game_starter.py").read_text(encoding="utf-8"))
    registered = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert "human-skill-full-v2" in registered

