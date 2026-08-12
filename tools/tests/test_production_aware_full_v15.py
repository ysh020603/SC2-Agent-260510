from SC2_Agent.human_skill_full_v15.prompt import PROCESS_CONTRACT
from SC2_Agent.human_skill_full_v15.saturation import conversion_alert, saturate_combat_queue


def _observation(
    *,
    minerals=1800,
    gas=300,
    used=50,
    cap=100,
    army=5,
    entities="",
    enemy="nothing scouted yet",
):
    return f"""[Economy] {minerals} minerals, {gas} vespene; income 1200 mins/min, 300 gas/min. Supply: {used}/{cap} (workers 44/44 current/ideal, army {army}).
[Own Forces & Infrastructure]
  Completed: {entities}.
  Active Queues: none.
[Enemy Intelligence] {enemy}."""


def test_early_alert_repairs_process_before_five_minutes():
    assert conversion_alert(_observation(minerals=600, gas=0, army=4), 180)
    assert not conversion_alert(_observation(minerals=250, gas=0, army=4), 180)


def test_buildable_producer_is_added_between_immediate_and_followup_batches():
    result = saturate_combat_queue(
        race="terran",
        obs_text=_observation(entities="1 BARRACKS, 1 SUPPLYDEPOT"),
        ordered_names=["Marine"],
        knowledge_candidates=[],
        game_time_seconds=360,
    )
    first_producer = result.index("Barracks")
    assert first_producer == 4
    assert set(result[:first_producer]) <= {"Marine", "Reaper"}
    assert result.count("Barracks") >= 1
    assert any(name in {"Marine", "Reaper"} for name in result[first_producer + 1 :])


def test_shared_renewable_resource_gets_database_derived_support_path():
    result = saturate_combat_queue(
        race="zerg",
        obs_text=_observation(entities="3 LARVA, 1 HATCHERY, 1 SPAWNINGPOOL, 1 OVERLORD"),
        ordered_names=["Zergling"],
        knowledge_candidates=[],
        game_time_seconds=360,
    )
    assert result.count("Zergling") >= 4
    assert "Queen" in result
    assert "Hatchery" in result


def test_confirmed_air_target_filters_ground_only_repetition():
    result = saturate_combat_queue(
        race="zerg",
        obs_text=_observation(
            entities="3 LARVA, 1 HATCHERY, 1 SPAWNINGPOOL, 1 OVERLORD",
            enemy="Composition: 3 VOIDRAY",
        ),
        ordered_names=["Zergling"],
        knowledge_candidates=["Queen"],
        game_time_seconds=360,
    )
    assert "Queen" in result
    assert "Zergling" not in result


def test_contract_names_mechanisms_not_race_or_matchup_rules():
    assert "production mechanism" in PROCESS_CONTRACT
    assert "target domain" in PROCESS_CONTRACT
    for race_name in ("Terran", "Protoss", "Zerg"):
        assert race_name not in PROCESS_CONTRACT
