"""Run the same fake observation through all six pinned Agent packages."""

from __future__ import annotations

import argparse
import json
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
from sc2_runtime import ensure_bundled_python_sc2

ensure_bundled_python_sc2()

from SC2_Agent.data_tools import race_prompt_context, race_unit_names, race_upgrade_names
from SC2_Agent.human_skill_common.skill_loader import ReadableSkillLoader, resolve_readable_skill_root
from SC2_Agent.human_skill_common.validation import resolve_api_config
from SC2_Agent.human_skill_common.variants import VARIANTS, load_variant_package
from tools.probe_human_skill_agent import SCENARIOS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-id", default="PvP_O01")
    parser.add_argument("--skill-root", default="")
    parser.add_argument("--api-config", default="")
    parser.add_argument("--model", default="DeepSeek-V4-flash")
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="ground_pressure")
    parser.add_argument("--live-llm", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    repo_root = REPO_ROOT
    fixture_root = os.path.join(repo_root, "tools", "tests", "fixtures", "readable_skills")
    skill_root = resolve_readable_skill_root(repo_root, args.skill_root or fixture_root)
    api_config = resolve_api_config(repo_root, args.api_config)
    rows = []
    for name in VARIANTS:
        spec, package, agent_class = load_variant_package(name)
        loader = ReadableSkillLoader(skill_root)
        skill = loader.load(
            method=spec.method,
            race="protoss",
            matchup="PvP",
            skill_id=args.skill_id,
            allowed_node_types=package.ALLOWED_NODE_TYPES,
            allow_graph_navigation=package.ALLOW_GRAPH_NAVIGATION,
        )
        count = 0

        def mock_llm(_messages, model_key, _config):
            nonlocal count
            count += 1
            content = (
                '{"type":"read_skill","node_id":"N001"}'
                if count == 1
                else '{"type":"decision","reason":"Live observation remains authoritative.","ordered_names":["Pylon"]}'
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
            trigger_reason="ablation_probe",
            game_time_seconds=300,
            decision_interval_seconds=60,
        )
        root_lower = skill.root_markdown.lower()
        rows.append(
            {
                "agent": name,
                "method": spec.method,
                "root_seen": bool(skill.root_markdown),
                "node_read": result.skill_reads_this_cycle,
                "negative_info_existed": "[negative]" in root_lower,
                "graph_navigation_existed": any(node.children for node in skill.nodes.values()),
                "final_queue": result.decision.ordered_names if result.decision else None,
                "llm_calls": len(result.llm_calls),
                "token_usage": [call["usage"] for call in result.llm_calls],
                "reasoning_present": any(call["reasoning_present"] for call in result.llm_calls),
                "is_reasoning_flags": [call["is_reasoning"] for call in result.llm_calls],
                "error": result.error,
            }
        )
    payload = {"scenario": args.scenario, "model": args.model, "rows": rows}
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(rendered + "\n")
    if any(
        row["error"]
        or (
            args.live_llm and (row["reasoning_present"] or any(flag is not False for flag in row["is_reasoning_flags"]))
        )
        for row in rows
    ):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
