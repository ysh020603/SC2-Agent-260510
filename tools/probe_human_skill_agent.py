"""Static READ_SKILL/memory/decision probe; does not start SC2."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
from sc2_runtime import ensure_bundled_python_sc2

ensure_bundled_python_sc2()

from SC2_Agent.data_tools import race_prompt_context, race_unit_names, race_upgrade_names
from SC2_Agent.human_skill_common.skill_loader import ReadableSkillLoader, resolve_readable_skill_root
from SC2_Agent.human_skill_common.validation import resolve_api_config
from SC2_Agent.human_skill_common.variants import VARIANTS, load_variant_package

SCENARIOS = {
    "ground_pressure": "Supply used/cap/free: 58/62/4. Enemy Intelligence remembers several Stalkers and an Immortal. Threat Flags: ground pressure possible.",
    "air_transition": "Supply used/cap/free: 66/78/12. Enemy Intelligence remembers Phoenixes and a Stargate. Air pressure is possible.",
    "greedy_opponent": "Resources: 620 minerals, 180 gas. Enemy Intelligence appears light while a possible expansion was observed.",
    "low_supply": "Supply used/cap/free: 61/62/1. Active Queues: Stalker. Under Construction: none.",
    "high_mineral_bank": "Resources: 1450 minerals, 240 gas. Supply free: 24. Production is light.",
    "missing_prerequisite": "Resources: 500 minerals, 300 gas. Completed: Nexus, Gateway. RoboticsFacility is not completed or under construction.",
    "protocol_read": "Static protocol exercise. Treat N001 details as required evidence: request READ_SKILL for N001 before producing the final decision.",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--human-skill-agent", choices=sorted(VARIANTS), default="human-skill-full")
    parser.add_argument("--skill-id", default="PvP_O01")
    parser.add_argument("--skill-root", default="")
    parser.add_argument("--api-config", default="")
    parser.add_argument("--model", default="DeepSeek-V4-flash")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="ground_pressure")
    parser.add_argument("--live-llm", action="store_true")
    args = parser.parse_args()

    repo_root = REPO_ROOT
    fixture_root = os.path.join(repo_root, "tools", "tests", "fixtures", "readable_skills")
    skill_root = resolve_readable_skill_root(repo_root, args.skill_root or fixture_root)
    api_config = resolve_api_config(repo_root, args.api_config)
    spec, package, agent_class = load_variant_package(args.human_skill_agent)
    loader = ReadableSkillLoader(skill_root)
    skill = loader.load(
        method=spec.method,
        race="protoss",
        matchup="PvP",
        skill_id=args.skill_id,
        allowed_node_types=package.ALLOWED_NODE_TYPES,
        allow_graph_navigation=package.ALLOW_GRAPH_NAVIGATION,
    )
    calls = 0

    def mock_llm(_messages, model_key, _config):
        nonlocal calls
        calls += 1
        content = (
            '{"type":"read_skill","node_id":"N001"}'
            if calls == 1
            else '{"type":"decision","reason":"I reconciled the readable guidance with live supply and prerequisites.","ordered_names":["Pylon"]}'
        )
        return {"content": content, "model_key": model_key, "model": "mock", "is_reasoning": False}

    kwargs = dict(loader=loader, skill=skill, model_key=args.model, api_config_path=api_config)
    if not args.live_llm:
        kwargs["llm_call"] = mock_llm
    agent = agent_class(**kwargs)
    result = agent.decide(
        race="protoss",
        enemy_race="protoss",
        obs_text=SCENARIOS[args.scenario],
        unfinished_canonical_names=[],
        canonical_unit_names=race_unit_names("protoss"),
        canonical_upgrade_names=race_upgrade_names("protoss"),
        race_context=race_prompt_context("protoss"),
        automation_context="Race-generic Protoss tactical automation.",
        decision_cycle=1,
        trigger_reason="static_probe",
        game_time_seconds=300,
        decision_interval_seconds=60,
    )
    output = {
        "agent": args.human_skill_agent,
        "method": spec.method,
        "scenario": args.scenario,
        "root_seen": bool(skill.root_markdown),
        "node_reads": result.skill_reads_this_cycle,
        "memory_after": result.skill_memory_after,
        "rounds": [asdict(item) for item in result.rounds],
        "decision": asdict(result.decision) if result.decision else None,
        "llm_calls": len(result.llm_calls),
        "reasoning_present": any(call["reasoning_present"] for call in result.llm_calls),
        "is_reasoning_flags": [call["is_reasoning"] for call in result.llm_calls],
        "errors": [call["error"] for call in result.llm_calls if call["error"]],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if result.decision is None:
        raise SystemExit(2)
    if args.live_llm and (
        output["reasoning_present"] or any(flag is not False for flag in output["is_reasoning_flags"])
    ):
        raise SystemExit("non-reasoning probe returned reasoning or ambiguous model metadata")


if __name__ == "__main__":
    main()
