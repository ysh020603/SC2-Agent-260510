from SC2_Agent.human_skill_common.skill_memory import MatchSkillMemory
from SC2_Agent.human_skill_common.trace_recorder import HumanSkillTraceRecorder


def test_memory_persists_across_decisions_and_resets_across_match():
    memory = MatchSkillMemory("PvP_O01", "full_signed_graph")
    assert memory.remember("N001", "body", node_type="positive", game_time=60, decision_cycle=1)
    assert not memory.remember("N001", "ignored", node_type="positive", game_time=120, decision_cycle=2)
    assert memory.visited_node_contents["N001"] == "body"
    assert memory.read_stats["N001"]["reuse_count"] == 1
    assert memory.read_stats["N001"]["decision_cycles_using_node"] == [1, 2]
    memory.reset()
    assert memory.visited_node_ids == []
    assert memory.visited_node_contents == {}


def test_skill_read_log_flushes_schema_five(tmp_path):
    memory = MatchSkillMemory("PvP_O01", "full_signed_graph")
    memory.remember("N001", "body", node_type="positive", game_time=60, decision_cycle=1)
    recorder = HumanSkillTraceRecorder(str(tmp_path), "probe")
    recorder.record_decision({"schema_version": 5, "cycle": 1})
    paths = recorder.flush(memory)
    assert paths["decisions"].endswith("probe.human_skill.json")
    assert paths["skill_reads"].endswith("probe.skill_reads.json")
    assert '"schema_version": 5' in (tmp_path / "probe.skill_reads.json").read_text()
    assert '"first_read_game_time": 60.0' in (tmp_path / "probe.skill_reads.json").read_text()
