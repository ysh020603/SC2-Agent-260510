from SC2_Agent.human_skill_full_v8.guard import prerequisite_error, race_macro_error


ZERG_OBS = """[Economy] 1000 minerals, 0 vespene; income 1000 mins/min, 0 gas/min. Supply: 20/44 (workers 20/20 current/ideal, army 0).
[Own Forces & Infrastructure]
  Completed: 20 DRONE, 6 LARVA, 4 OVERLORD, 2 HATCHERY.
  Under Construction: none.
"""

TERRAN_OBS = """[Economy] 1500 minerals, 500 vespene; income 1200 mins/min, 340 gas/min. Supply: 40/80 (workers 32/22 current/ideal, army 8).
[Own Forces & Infrastructure]
  Completed: 32 SCV, 8 SUPPLYDEPOT, 1 BARRACKS, 1 COMMANDCENTER.
  Under Construction: none.
"""


def test_v8_requires_zerg_defense_prerequisite_and_larva_conversion():
    assert "SpawningPool" in race_macro_error(
        race="zerg", obs_text=ZERG_OBS, ordered_names=["Drone", "Overlord"], game_time_seconds=120
    )
    repaired = ["SpawningPool"] + ["Zergling"] * 8
    assert not race_macro_error(race="zerg", obs_text=ZERG_OBS, ordered_names=repaired, game_time_seconds=120)
    assert not prerequisite_error(race="zerg", obs_text=ZERG_OBS, ordered_names=repaired)


def test_v8_rejects_dependent_zerg_unit_before_tech_chain():
    error = prerequisite_error(
        race="zerg",
        obs_text=ZERG_OBS,
        ordered_names=["Hydralisk", "Lair", "HydraliskDen"],
    )
    assert "Hydralisk" in error
    assert "missing" in error


def test_v8_converts_terran_bank_into_production_before_units():
    error = race_macro_error(
        race="terran",
        obs_text=TERRAN_OBS,
        ordered_names=["SCV", "SCV"] + ["Marine"] * 8,
        game_time_seconds=300,
    )
    assert "SCV" in error
    repaired = ["Barracks"] + ["Marine"] * 8
    assert not race_macro_error(
        race="terran", obs_text=TERRAN_OBS, ordered_names=repaired, game_time_seconds=300
    )
