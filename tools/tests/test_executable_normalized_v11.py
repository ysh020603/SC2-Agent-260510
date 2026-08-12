from SC2_Agent.human_skill_full_v11.normalize import normalize_early_queue

Z = """[Economy] 900 minerals, 0 vespene; income 700 mins/min, 0 gas/min. Supply: 30/60 (workers 30/30 current/ideal, army 2).
[Own Forces & Infrastructure]
  Completed: 30 DRONE, 2 OVERLORD, 1 HATCHERY, 1 SPAWNINGPOOL.
[Enemy Intelligence] none."""
T = """[Economy] 1100 minerals, 0 vespene; income 700 mins/min, 0 gas/min. Supply: 35/60 (workers 32/28 current/ideal, army 5).
[Own Forces & Infrastructure]
  Completed: 32 SCV, 2 SUPPLYDEPOT, 1 COMMANDCENTER, 1 BARRACKS.
[Enemy Intelligence] none."""

def test_zerg_normalization_converts_larva_without_rejection():
    result = normalize_early_queue(race="zerg", obs_text=Z, ordered_names=["Drone"] * 6 + ["Overlord"], game_time_seconds=150)
    assert result.count("Drone") == 0 and result.count("Overlord") == 0 and result.count("Zergling") == 10

def test_terran_normalization_adds_throughput_and_combat():
    result = normalize_early_queue(race="terran", obs_text=T, ordered_names=["SCV"] * 5, game_time_seconds=200)
    assert result.count("SCV") == 2 and "Barracks" in result and result.count("Marine") == 10

def test_normalization_is_inert_outside_failure_window():
    assert normalize_early_queue(race="zerg", obs_text=Z, ordered_names=["Drone"], game_time_seconds=40) == ["Drone"]
