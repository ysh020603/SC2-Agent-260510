#!/usr/bin/env python3
"""Freeze the legacy strategy-tools inventory without importing its modules."""

from __future__ import annotations

import ast
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ATTACK_RE = re.compile(r"PlanZoneAttack\s*\(([^)]*)\)")
THRESHOLD_RE = re.compile(r"attack_threshold\s*=\s*([0-9]+(?:\.[0-9]+)?)")
ATTACK_VALUE_RE = re.compile(r"attack_value\s*=\s*([0-9]+(?:\.[0-9]+)?)")
GATE_WORDS = ("TechReady", "UnitReady", "UnitExists", "attack_requirement")
SPECIAL_WORDS = ("TacticalJump", "DodgeRamp", "WorkerAttack", "ForceField")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=str(ROOT), text=True).strip()


def inventory_file(path):
    text = path.read_text(encoding="utf-8")
    relative = path.relative_to(ROOT).as_posix()
    parts = relative.split("/")
    tree = ast.parse(text)
    classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    thresholds = THRESHOLD_RE.findall(text) + ATTACK_VALUE_RE.findall(text)
    plan_args = [match.strip() for match in ATTACK_RE.findall(text)]
    return {
        "path": relative,
        "race": parts[1],
        "strategy": parts[2],
        "declared_attack_thresholds": thresholds,
        "plan_zone_attack_arguments": plan_args,
        "attack_gate_markers": [word for word in GATE_WORDS if word in text],
        "special_behavior_markers": [word for word in SPECIAL_WORDS if word in text],
        "classes": classes,
    }


def main():
    files = sorted(ROOT.glob("SKILL/*/*/strategy_tools.py"))
    records = [inventory_file(path) for path in files]
    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline_commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "strategy_tools_count": len(records),
        "migration_policy": "legacy files retained; Human Skill Agent loading disabled",
        "records": records,
    }
    (ROOT / "TACTICAL_MIGRATION_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Legacy Tactical Strategy Tools Inventory",
        "",
        "Generated from the frozen pre-migration strategy tool files. These files remain for baseline compatibility;",
        "the Human Skill Agent no longer imports them.",
        "",
        "| Race | Strategy | Threshold declarations | PlanZoneAttack args | Gates | Special markers |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in records:
        values = [
            item["race"],
            item["strategy"],
            ", ".join(item["declared_attack_thresholds"]) or "—",
            ", ".join(item["plan_zone_attack_arguments"]) or "—",
            ", ".join(item["attack_gate_markers"]) or "—",
            ", ".join(item["special_behavior_markers"]) or "—",
        ]
        lines.append("| " + " | ".join(value.replace("|", "\\|") for value in values) + " |")
    lines.extend(
        [
            "",
            "## V1 migration boundary",
            "",
            "- All thresholds and gates above are legacy-only and are not loaded by `UniversalLLMBot`.",
            "- Strategy-specific combat helpers remain untouched for reproducible baselines.",
            "- New runs use the one frozen `UNIVERSAL_TACTICS_V1_CONFIG.json` configuration.",
        ]
    )
    output = ROOT / "docs" / "tactical_strategy_tools_inventory.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
