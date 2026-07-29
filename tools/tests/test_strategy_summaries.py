from pathlib import Path

from SC2_Agent.top_agent import parse_strategy_summary


ROOT = Path(__file__).resolve().parents[2]


def test_all_strategy_files_are_summary_only():
    files = sorted((ROOT / "SKILL" / "terran").glob("*/Top_agent_*.md"))
    assert len(files) == 57
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert text.lstrip().startswith("# Summary")
        assert "# Details" not in text
        assert "[Step " not in text
        assert parse_strategy_summary(text)
