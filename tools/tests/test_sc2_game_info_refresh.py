from sc2.main import _game_info_refresh_due


def test_game_info_refresh_interval_is_bounded() -> None:
    assert not _game_info_refresh_due(
        current_game_loop=111,
        last_refresh_game_loop=0,
        interval_game_loops=112,
    )
    assert _game_info_refresh_due(
        current_game_loop=112,
        last_refresh_game_loop=0,
        interval_game_loops=112,
    )


def test_zero_interval_preserves_upstream_every_step_behavior() -> None:
    assert _game_info_refresh_due(
        current_game_loop=1,
        last_refresh_game_loop=0,
        interval_game_loops=0,
    )
