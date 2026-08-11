"""Regression tests for player-mode selection in GameStarter."""

from bot_loader.game_starter import _is_human_player_spec


def test_real_human_player_specs_enable_human_mode():
    assert _is_human_player_spec("human")
    assert _is_human_player_spec("human.protoss")


def test_bot_name_containing_human_remains_a_bot():
    assert not _is_human_player_spec("universal_llm_human_skill.protoss")
    assert not _is_human_player_spec("human_skill_bot.zerg")
