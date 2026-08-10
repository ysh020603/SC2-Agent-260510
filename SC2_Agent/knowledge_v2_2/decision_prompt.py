"""Independent prompt assembly for the knowledge-assisted macro agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent

OBSERVATION_FIELD_GUIDE = """\
* Time: current in-game clock for this decision, not wall-clock or API time.
* Resources: current minerals and vespene. Income is an estimated amount per in-game minute, not resources already available.
* Supply used/cap/free: used army plus worker supply, current maximum, and cap minus used. Supply providers under construction do not count in cap yet.
* Workers current/ideal: living workers versus displayed saturation slots of ready town halls and gas structures. It is an economic guide, not a mandatory final target.
* Army supply is combat-unit supply, not unit count or the combat analyzer power value.
* Completed contains ready own units and structures. Under Construction includes unfinished foundations, morphs, and units already in production.
* Workers En Route means a worker has a build order but no visible foundation yet. Treat it as committed work.
* Active Queues are production, morph, or research orders accepted by the engine. Do not duplicate them solely because they are absent from Completed.
* Enemy Intelligence contains remembered observations, not omniscient live vision. Stale units may already be dead or elsewhere.
* Map Control reports owned, enemy, and contested zones inferred by the zone manager.
* Army and Income Advantage are relative estimates. Positive favors us and negative favors the enemy.
* Power is an abstract combat-analyzer estimate used by automated attack and defense logic. It is not supply, unit count, or a guaranteed outcome.
* Losses are observed cumulative resource-value losses.
* Research and Technology lists completed upgrades. Research currently running appears in Active Queues.
* Threat Flags are detector or build-analyzer warnings, not certainty about unseen plans."""


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8").strip()


def build_knowledge_decision_context(
    *,
    race: str,
    strategy_summary: str,
    obs_text: str,
    unfinished_canonical_names: list[str],
    canonical_unit_names: list[str],
    canonical_upgrade_names: list[str],
    race_context: str = "",
    strategy_automation_context: str = "",
    decision_cycle: int = 1,
    trigger_reason: str = "initial_decision",
    game_time_seconds: float = 0.0,
    decision_interval_seconds: float = 60.0,
    enemy_race: str = "unknown",
) -> dict[str, Any]:
    """Build version-local MainAgent system and decision-event messages."""

    race_name = race.lower()
    interval = f"{decision_interval_seconds:g}"
    lifecycle = f"""\
* A decision is triggered once at game start and every configured {interval} in-game seconds.
* It may trigger early when a previously non-empty macro queue becomes drained, but never sooner than 5 in-game seconds after the previous decision.
* Each decision receives a fresh observation and only canonical names from the previous queue that have not yet been committed to the SC2 engine.
* Previous explanations and completed queue history are not carried forward. Infer continuity from the fresh observation, strategy objective, and uncommitted names.
* An accepted response atomically replaces all uncommitted tasks. Engine-accepted work remains untouched.
* Invalid output, or a non-empty decision with no executable mapped tasks, is rejected and the old queue remains active."""
    worker_name = {
        "terran": "SCV",
        "protoss": "Probe",
        "zerg": "Drone",
    }.get(race_name, "worker")
    replacements = {
        "{{RACE_CAP}}": race_name.capitalize(),
        "{{DECISION_LIFECYCLE}}": lifecycle,
        "{{RACE_CONTEXT}}": race_context.strip() or "(none)",
        "{{WORKER_NAME}}": worker_name,
        "{{STRATEGY_SUMMARY}}": strategy_summary.strip() or "(none)",
        "{{AUTOMATION_CONTEXT}}": strategy_automation_context.strip()
        or "No strategy automation profile was supplied.",
        "{{OBSERVATION_FIELD_GUIDE}}": OBSERVATION_FIELD_GUIDE,
        "{{CANONICAL_UNITS}}": ", ".join(canonical_unit_names),
        "{{CANONICAL_UPGRADES}}": ", ".join(canonical_upgrade_names),
    }
    system = _read("prompts/main_system.md")
    for marker, value in replacements.items():
        system = system.replace(marker, value)
    unresolved = [marker for marker in replacements if marker in system]
    if unresolved:
        raise ValueError(f"Unresolved knowledge prompt markers: {unresolved}")

    user = (
        "[Decision Event]\n"
        f"Cycle: {int(decision_cycle)}\n"
        f"Trigger: {trigger_reason}\n"
        f"Game time: {float(game_time_seconds):.1f} seconds\n"
        f"Configured interval: {float(decision_interval_seconds):g} seconds\n\n"
        f"Opponent race: {str(enemy_race).capitalize()}\n\n"
        f"[Current Observation]\n{obs_text or '(empty)'}\n\n"
        "[Carry-over Uncommitted Tasks]\n"
        f"{json.dumps(unfinished_canonical_names, ensure_ascii=False)}\n\n"
        "[Replacement Reminder]\n"
        "These uncommitted names will be discarded when this decision is accepted. "
        "Re-include the important ones in ordered_names."
    )
    return {
        "system_prompt": system,
        "decision_event": user,
        "metadata": {
            "race": race_name,
            "enemy_race": str(enemy_race).lower(),
            "decision_cycle": int(decision_cycle),
            "trigger_reason": trigger_reason,
            "game_time_seconds": float(game_time_seconds),
            "decision_interval_seconds": float(decision_interval_seconds),
            "canonical_unit_count": len(canonical_unit_names),
            "canonical_upgrade_count": len(canonical_upgrade_names),
        },
    }


__all__ = ["OBSERVATION_FIELD_GUIDE", "build_knowledge_decision_context"]
