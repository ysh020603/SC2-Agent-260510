from SC2_Agent.human_skill_full_v13.agent import HumanSkillFullV13Agent, _combat_actions
from SC2_Agent.human_skill_full_v13.prompt import PROCESS_CONTRACT


LOW_ARMY = """[Economy] 900 minerals, 100 vespene; income 1200 mins/min, 200 gas/min. Supply: 50/90 (workers 44/44 current/ideal, army 6).
[Own Forces & Infrastructure]
  Completed: 44 SCV, 1 COMMANDCENTER, 1 BARRACKS.
[Enemy Intelligence] nothing scouted yet."""


def test_contract_is_process_level_and_preserves_negative_experience():
    assert "NEGATIVE node" in PROCESS_CONTRACT
    assert "resource" in PROCESS_CONTRACT.lower() and "two decisions" in PROCESS_CONTRACT.lower()
    for race_specific in ("Marine", "Zergling", "Stalker", "Terran", "Zerg", "Protoss"):
        assert race_specific not in PROCESS_CONTRACT


def test_cross_race_combat_detection_uses_database_roles():
    assert _combat_actions("terran", ["SCV", "SupplyDepot", "Marine"]) == ["Marine"]
    assert _combat_actions("zerg", ["Drone", "Overlord", "Zergling"]) == ["Zergling"]
    assert _combat_actions("protoss", ["Probe", "Pylon", "Stalker"]) == ["Stalker"]


def test_conversion_alert_rejects_queue_without_combat_candidate():
    agent = object.__new__(HumanSkillFullV13Agent)
    error = agent._variant_decision_error(
        race="terran", obs_text=LOW_ARMY, ordered_names=["SCV", "CommandCenter"], game_time_seconds=360
    )
    assert "resource-to-army conversion failure" in error
    assert agent._variant_decision_error(
        race="terran", obs_text=LOW_ARMY, ordered_names=["Marine"], game_time_seconds=360
    ) == ""
