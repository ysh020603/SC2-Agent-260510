from sharpy.managers.core.cooldown_manager import _available_abilities_refresh_due


def test_available_abilities_refresh_is_throttled() -> None:
    assert not _available_abilities_refresh_due(
        current_game_loop=43,
        last_refresh_game_loop=0,
        interval_game_loops=44,
    )
    assert _available_abilities_refresh_due(
        current_game_loop=44,
        last_refresh_game_loop=0,
        interval_game_loops=44,
    )


def test_available_abilities_refresh_interval_is_always_positive() -> None:
    assert not _available_abilities_refresh_due(
        current_game_loop=0,
        last_refresh_game_loop=0,
        interval_game_loops=0,
    )
    assert _available_abilities_refresh_due(
        current_game_loop=1,
        last_refresh_game_loop=0,
        interval_game_loops=0,
    )
