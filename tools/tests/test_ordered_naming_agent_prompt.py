from SC2_Agent.ordered_naming_agent import (
    build_ordered_naming_messages,
    parse_ordered_naming_response,
)


def test_ordered_naming_prompt_uses_naming_contract_but_outputs_ordered_names():
    messages = build_ordered_naming_messages(
        race="terran",
        plan_text="Open with depot, rax, tech lab, then train three marines.",
        terran_unit_names=["SupplyDepot", "Barracks", "BarracksTechLab", "Marine"],
        terran_upgrade_names=["Stimpack"],
        obs_text="CommandCenter: 1 completed",
        strategy_summary="Bio pressure.",
    )

    system_msg = messages[0]["content"]

    assert "[Name Hints: Jargon and Upgrade Categories]" in system_msg
    assert "Every output name must still exactly match" in system_msg
    assert "Do NOT output counts" in system_msg
    assert "Repeat a name when multiple copies are needed" in system_msg
    assert '"ordered_names"' in system_msg
    assert "Do NOT output action/ability names" in system_msg


def test_parse_ordered_naming_response_accepts_fenced_json_and_filters_bad_items():
    raw = """```json
{"ordered_names":["Barracks", "", 42, "Marine", "Marine"]}
```"""

    assert parse_ordered_naming_response(raw) == ["Barracks", "Marine", "Marine"]


def test_parse_ordered_naming_response_rejects_wrong_shape():
    assert parse_ordered_naming_response('{"items":[{"name":"Marine","count":2}]}') is None
