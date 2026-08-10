from pathlib import Path

from bot_loader.game_starter import artifact_file_name
from run_vs_ai import build_match_id


def test_default_match_paths_stay_below_windows_max_path():
    match_id = build_match_id(
        timestamp="20260730_123456",
        my_bot_name="universal_llm",
        enemy_race="terran",
        enemy_difficulty="veryhard",
        enemy_build="random",
        map_name="KairosJunctionLE",
        bot_race="protoss",
        decision_model="DeepSeek-V4-flash_think",
        decision_interval=60,
        run_index=12345,
    )
    assert len(match_id) <= 64

    record_dir = (
        Path(r"C:\code\SC2_Agent_add_knowledge\SC2-Agent-knowlegde")
        / "game_records"
        / "kimi_nothink_full_matrix_20260730"
        / match_id
    )
    artifact = artifact_file_name(str(record_dir), match_id, "fallback")
    assert artifact == "match"
    assert len(str(record_dir / f"{artifact}.SC2Replay")) < 260


def test_artifact_name_keeps_match_id_without_an_explicit_record_directory():
    assert artifact_file_name(None, "match_123", "fallback") == "match_123"
    assert artifact_file_name(None, None, "fallback") == "fallback"
