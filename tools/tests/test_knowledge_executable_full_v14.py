from SC2_Agent.human_skill_full_v14.prompt import PROCESS_CONTRACT
from SC2_Agent.human_skill_full_v14.saturation import conversion_alert, saturate_combat_queue


def _observation(*, minerals=1000, gas=200, used=50, cap=90, army=6, entities=""):
    return f"""[Economy] {minerals} minerals, {gas} vespene; income 1200 mins/min, 300 gas/min. Supply: {used}/{cap} (workers 44/44 current/ideal, army {army}).
[Own Forces & Infrastructure]
  Completed: {entities}.
  Active Queues: none.
[Enemy Intelligence] nothing scouted yet."""


def test_contract_and_runtime_are_process_level_not_matchup_rules():
    assert "single combat entry" in PROCESS_CONTRACT
    assert "knowledge overlay" in PROCESS_CONTRACT.lower()
    assert "Enemy Intelligence" in PROCESS_CONTRACT


def test_alert_covers_low_army_and_severe_unspent_bank():
    assert conversion_alert(_observation(), 360)
    assert conversion_alert(_observation(minerals=2500, gas=500, used=120, cap=180, army=55), 720)
    assert not conversion_alert(_observation(minerals=200, gas=100, army=20), 360)


def test_database_driven_saturation_works_for_all_three_races():
    cases = [
        ("terran", "1 BARRACKS", ["Marine"]),
        ("protoss", "1 GATEWAY, 1 CYBERNETICSCORE", ["Zealot"]),
        ("zerg", "3 LARVA, 1 HATCHERY, 1 SPAWNINGPOOL", ["Zergling"]),
    ]
    for race, entities, ordered in cases:
        result = saturate_combat_queue(
            race=race,
            obs_text=_observation(entities=entities),
            ordered_names=ordered,
            knowledge_candidates=[],
            game_time_seconds=360,
        )
        assert len(result) >= 6
        assert result.count(ordered[0]) >= 6


def test_saturation_frontloads_supply_and_discards_optional_crowding():
    result = saturate_combat_queue(
        race="terran",
        obs_text=_observation(used=88, cap=90, entities="1 BARRACKS"),
        ordered_names=["SCV", "CommandCenter", "Marine"],
        knowledge_candidates=[],
        game_time_seconds=360,
    )
    assert result[0] == "SupplyDepot"
    assert "SCV" not in result and "CommandCenter" not in result
    assert result.count("Marine") >= 6
