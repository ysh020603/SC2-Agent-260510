from SC2_Agent.decision_agent import (
    build_decision_messages,
    parse_decision_response,
)


def test_prompt_defines_replacement_and_unmanaged_supply_contract():
    messages = build_decision_messages(
        race="terran",
        strategy_summary="Bio pressure into a mech transition.",
        obs_text="Supply: 30/31, free 1. Factory construction is in progress.",
        unfinished_canonical_names=["Barracks", "Marine", "Marine"],
        canonical_unit_names=["SupplyDepot", "Barracks", "Marine"],
        canonical_upgrade_names=["Stimpack"],
    )
    system = messages[0]["content"]
    user = messages[1]["content"]

    assert "COMPLETE new queue" in system
    assert "Re-include every still-important item" in system
    assert "Supply is NOT managed by downstream code" in system
    assert "normally no more than 20 names" in system
    assert "not chain-of-thought" in system
    assert "Bio pressure into a mech transition." in system
    assert '["Barracks", "Marine", "Marine"]' in user
    assert "will be discarded" in user
    assert "PENDING" not in user


def test_parser_accepts_reason_and_empty_queue():
    parsed = parse_decision_response(
        '{"reason":"Committed work is sufficient for now.","ordered_names":[]}'
    )
    assert parsed is not None
    assert parsed.reason == "Committed work is sufficient for now."
    assert parsed.ordered_names == []


def test_parser_preserves_order_and_repetition():
    parsed = parse_decision_response(
        '```json\n{"reason":"Add production.","ordered_names":'
        '["SupplyDepot","Barracks","Marine","Marine"]}\n```'
    )
    assert parsed is not None
    assert parsed.ordered_names == [
        "SupplyDepot",
        "Barracks",
        "Marine",
        "Marine",
    ]


def test_parser_rejects_missing_public_reason_or_bad_shape():
    assert parse_decision_response('{"ordered_names":["Marine"]}') is None
    assert parse_decision_response('{"reason":"x","ordered_names":"Marine"}') is None
