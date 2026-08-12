from SC2_Agent.human_skill_full_v16.saturation import saturate_combat_queue as saturate_v16
from SC2_Agent.human_skill_full_v18.prompt import PROCESS_CONTRACT
from SC2_Agent.human_skill_full_v18.saturation import conversion_alert, saturate_combat_queue


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


def test_expansion_mode_structure_is_treated_as_combat_production_capacity():
    result = saturate_combat_queue(
        race="zerg",
        obs_text=_observation(
            minerals=3000,
            gas=1000,
            entities="3 LARVA, 1 HATCHERY, 1 SPAWNINGPOOL, 1 OVERLORD",
            enemy="Composition: 3 VOIDRAY",
        ),
        ordered_names=["Queen"],
        knowledge_candidates=[],
        game_time_seconds=600,
    )
    assert result.count("Hatchery") >= 1


def test_persistent_capability_gap_queues_knowledge_prerequisite_chain():
    result = saturate_combat_queue(
        race="zerg",
        obs_text=_observation(
            minerals=3000,
            gas=2000,
            entities="3 LARVA, 1 HATCHERY, 1 SPAWNINGPOOL, 1 OVERLORD",
            enemy="Composition: 3 VOIDRAY",
        ),
        ordered_names=["Zergling"],
        knowledge_candidates=["Hydralisk"],
        game_time_seconds=600,
        repair_level=1,
    )
    assert result.index("Lair") < result.index("HydraliskDen") < result.index("Hydralisk")


def test_contract_names_mechanisms_not_race_or_matchup_rules():
    assert "production mechanism" in PROCESS_CONTRACT
    assert "target domain" in PROCESS_CONTRACT
    for race_name in ("Terran", "Protoss", "Zerg"):
        assert race_name not in PROCESS_CONTRACT


def test_early_midgame_queue_is_identical_to_v16():
    kwargs = dict(
        race="terran",
        obs_text=_observation(entities="1 BARRACKS, 1 SUPPLYDEPOT"),
        ordered_names=["Marine"],
        knowledge_candidates=[],
        game_time_seconds=600,
        repair_level=2,
    )
    assert saturate_combat_queue(**kwargs) == saturate_v16(**kwargs)


def test_late_game_closer_adds_income_matched_throughput():
    kwargs = dict(
        race="terran",
        obs_text=_observation(minerals=5000, gas=1000, entities="1 BARRACKS, 1 SUPPLYDEPOT"),
        ordered_names=["Marine"],
        knowledge_candidates=[],
        game_time_seconds=960,
    )
    v18 = saturate_combat_queue(**kwargs)
    v16 = saturate_v16(**kwargs)
    assert v18.count("Barracks") > v16.count("Barracks")
    assert v18.count("Marine") > v16.count("Marine")
