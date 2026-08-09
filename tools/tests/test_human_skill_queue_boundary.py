from SC2_Agent.human_skill_common.skill_loader import ReadableSkillLoader
from SC2_Agent.human_skill_common.variants import load_variant_package


def _agent(fixture_skill_root, api_config, responses):
    spec, package, agent_class = load_variant_package("human-skill-full")
    loader = ReadableSkillLoader(str(fixture_skill_root))
    skill = loader.load(
        method=spec.method,
        race="protoss",
        matchup="PvP",
        skill_id="PvP_O01",
        allowed_node_types=package.ALLOWED_NODE_TYPES,
        allow_graph_navigation=package.ALLOW_GRAPH_NAVIGATION,
    )

    def call(*_):
        return {
            "content": responses.pop(0),
            "model_key": "DeepSeek-V4-flash",
            "model": "deepseek-v4-flash",
            "is_reasoning": False,
        }

    return agent_class(
        loader=loader, skill=skill, model_key="DeepSeek-V4-flash", api_config_path=str(api_config), llm_call=call
    )


def _kwargs(cycle=1):
    return dict(
        race="protoss",
        enemy_race="protoss",
        obs_text="Supply free: 2. Enemy Intelligence: Stalker.",
        unfinished_canonical_names=[],
        canonical_unit_names=["Pylon", "Stalker"],
        canonical_upgrade_names=[],
        race_context="Protoss mechanics.",
        automation_context="generic",
        decision_cycle=cycle,
        trigger_reason="probe",
        game_time_seconds=60 * cycle,
        decision_interval_seconds=60,
    )


def test_read_skill_never_crosses_queue_boundary_and_final_does(fixture_skill_root, api_config):
    agent = _agent(
        fixture_skill_root,
        api_config,
        [
            '{"type":"read_skill","node_id":"N001"}',
            '{"type":"decision","reason":"avoid a supply block","ordered_names":["Pylon"]}',
        ],
    )
    scheduler_calls = []
    result = agent.decide(**_kwargs())
    assert result.rounds[0].type == "read_skill"
    assert scheduler_calls == []
    if result.decision is not None:
        scheduler_calls.append(result.decision.ordered_names)
    assert scheduler_calls == [["Pylon"]]
    assert agent.memory.visited_node_ids == ["N001"]


def test_read_memory_is_present_next_decision(fixture_skill_root, api_config):
    agent = _agent(
        fixture_skill_root,
        api_config,
        [
            '{"type":"read_skill","node_id":"N001"}',
            '{"type":"decision","reason":"stabilize","ordered_names":["Stalker"]}',
            '{"type":"decision","reason":"continue","ordered_names":[]}',
        ],
    )
    first = agent.decide(**_kwargs(1))
    second = agent.decide(**_kwargs(2))
    assert first.skill_memory_after == ["N001"]
    assert second.skill_memory_before == ["N001"]
    assert "N001 — Stabilize" in second.llm_calls[0]["messages"][0]["content"]


def test_repeated_read_is_served_from_memory(fixture_skill_root, api_config):
    agent = _agent(
        fixture_skill_root,
        api_config,
        [
            '{"type":"read_skill","node_id":"N001"}',
            '{"type":"decision","reason":"first","ordered_names":[]}',
            '{"type":"read_skill","node_id":"N001"}',
            '{"type":"decision","reason":"second","ordered_names":[]}',
        ],
    )
    agent.decide(**_kwargs(1))
    agent.navigator.read = lambda _node_id: (_ for _ in ()).throw(AssertionError("disk read"))
    second = agent.decide(**_kwargs(2))
    assert second.decision.reason == "second"
    assert agent.memory.read_stats["N001"]["reuse_count"] == 1


def test_invalid_responses_keep_old_queue_semantics(fixture_skill_root, api_config):
    agent = _agent(fixture_skill_root, api_config, ["bad"] * 5)
    result = agent.decide(**_kwargs())
    assert result.decision is None
    assert result.error == "invalid_response_keep_old_queue"
    assert len(result.llm_calls) == 5


def test_first_match_decision_must_read_skill_node(fixture_skill_root, api_config):
    agent = _agent(
        fixture_skill_root,
        api_config,
        [
            '{"type":"decision","reason":"too early","ordered_names":["Pylon"]}',
            '{"type":"read_skill","node_id":"N001"}',
            '{"type":"decision","reason":"grounded","ordered_names":["Pylon"]}',
        ],
    )
    result = agent.decide(**_kwargs())
    assert [item.type for item in result.rounds] == ["invalid", "read_skill", "decision"]
    assert result.skill_reads_this_cycle == ["N001"]
    assert result.decision.reason == "grounded"


def test_gas_cost_queue_is_repaired_by_llm_before_acceptance(fixture_skill_root, api_config):
    agent = _agent(
        fixture_skill_root,
        api_config,
        [
            '{"type":"read_skill","node_id":"N001"}',
            '{"type":"decision","reason":"tech","ordered_names":["Stalker"]}',
            '{"type":"decision","reason":"fund tech","ordered_names":["Assimilator","Stalker"]}',
        ],
    )
    kwargs = _kwargs()
    kwargs["obs_text"] = (
        "[Economy] 400 minerals, 0 vespene; income 900 mins/min, 0 gas/min.\n"
        "[Own Forces & Infrastructure]\nCompleted: 1 GATEWAY, 1 CYBERNETICSCORE.\n"
        "[Enemy Intelligence] 1 ASSIMILATOR."
    )
    kwargs["canonical_unit_names"] = ["Assimilator", "Pylon", "Stalker"]
    result = agent.decide(**kwargs)
    assert [item.type for item in result.rounds] == ["read_skill", "invalid", "decision"]
    assert "no own Assimilator" in result.rounds[1].error
    assert result.decision.ordered_names == ["Assimilator", "Stalker"]
