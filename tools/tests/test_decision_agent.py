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
        race_context="Supply provider: SupplyDepot",
        strategy_automation_context=(
            "Attack trigger: combat-power threshold reaches 26."
        ),
        decision_cycle=3,
        trigger_reason="queue_drained",
        game_time_seconds=125.5,
        decision_interval_seconds=60,
        enemy_race="zerg",
    )
    system = messages[0]["content"]
    user = messages[1]["content"]

    assert "COMPLETE new queue" in system
    assert "Re-include every still-important unfinished item" in system
    assert "Queue order is priority, not a" in system
    assert "timing lock" in system
    assert "SupplyDepot, Pylon, and Overlord each add 8" in system
    assert "normally 1, or 2-3" in system
    assert "Never fill most or all of the queue with supply" in system
    assert "worker production, and bank spending are all your macro" in system
    assert "repeated SCV" in system
    assert "75% of displayed ideal" in system
    assert "no more workers than the current-to-ideal gap" in system
    assert "2-4 additional workers" in system
    assert "70-80 SCVs/Probes" in system
    assert "If minerals exceed roughly 1000" in system
    assert "normally no more than 20 names" in system
    assert "not chain-of-thought" in system
    assert "Bio pressure into a mech transition." in system
    assert "Supply provider: SupplyDepot" in system
    assert "combat-power threshold reaches 26" in system
    assert "Workers En Route" in system
    assert "abstract combat-analyzer strength estimate" in system
    assert "Research currently running" in system
    assert "every configured 60 in-game seconds" in system
    assert "does not insert missing prerequisites" in system
    assert '["Barracks", "Marine", "Marine"]' in user
    assert "will be discarded" in user
    assert "Cycle: 3" in user
    assert "Trigger: queue_drained" in user
    assert "Game time: 125.5 seconds" in user
    assert "Opponent race: Zerg" in user
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
