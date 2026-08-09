from SC2_Agent.human_skill_common.protocol import parse_agent_response


def test_read_skill_protocol():
    parsed = parse_agent_response('{"type":"read_skill","node_id":"N001"}')
    assert parsed.request.node_id == "N001"
    assert parsed.decision is None


def test_final_decision_protocol():
    parsed = parse_agent_response('{"type":"decision","reason":"stabilize","ordered_names":["Pylon"]}')
    assert parsed.decision.ordered_names == ["Pylon"]


def test_unknown_fields_and_types_rejected():
    assert parse_agent_response('{"type":"read_skill","node_id":"N001","path":"../../x"}').error
    assert parse_agent_response('{"type":"decision","reason":"x","ordered_names":"Pylon"}').error


def test_decision_queue_has_a_hard_length_limit():
    names = ",".join('"Stalker"' for _ in range(41))
    parsed = parse_agent_response(
        '{"type":"decision","reason":"too long","ordered_names":[' + names + "]}"
    )
    assert "at most 40" in parsed.error
