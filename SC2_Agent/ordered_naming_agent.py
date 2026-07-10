"""Ordered Naming Agent prompt construction and parsing.

This agent is used by the optional two-stage decision mode. It merges the
current Naming and Ordering LLM responsibilities: read a strategy step plus the
current observation, then return an already ordered flat list of canonical
Unit/Upgrade names. Repeated names represent repeated production requests.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("SC2_Agent.ordered_naming_agent")


def build_ordered_naming_messages(
    race: str,
    plan_text: str,
    terran_unit_names: List[str],
    terran_upgrade_names: List[str],
    obs_text: str = "",
    strategy_summary: str = "",
) -> List[Dict[str, str]]:
    """Build the Ordered Naming Agent prompt.

    The prompt body intentionally follows ``build_naming_messages`` closely, but
    the output contract is an ordered flat list instead of ``name/count`` pairs.
    """
    race_cap = race.capitalize()
    units_text = ", ".join(terran_unit_names)
    upgrades_text = ", ".join(terran_upgrade_names)
    summary_text = strategy_summary.strip() or "(none)"

    system_msg = f"""You read one natural-language {race_cap} strategy step plus the current game
observation. Extract the concrete structure / unit / upgrade INCREMENTS that
should be issued now, using ONLY canonical entity names from the Canonical Name
List below, and return them in a sensible execution order.

[Strategy Summary]
{summary_text}

The Strategy Summary describes the overall game plan (composition, timings,
late-game direction). Use it as macro guidance to interpret the current step,
but the [Strategy Step] in the user message remains the authoritative source
of what to issue this cycle.

Rules:
* Read the step and the observation together. The step is the strategic
  requirement; the observation shows what already exists or is in progress.
  Enumerate the missing increments needed to satisfy this step now.
* Return a flat ordered list of canonical Unit/Upgrade names. Do NOT output counts.
  If the same entity should be produced multiple times, repeat its name
  multiple times in the list.
* Order the names for efficient execution: prerequisite and tech-bottleneck
  structures before the units/upgrades that depend on them; cheap/unlocking
  actions before expensive follow-up; supply headroom before supply-consuming
  training when the step asks for supply.
* The step may mix precise quantities (e.g. "build 3 Barracks") with vague
  language (e.g. "a few", "some", "enough", "more", "ramp up", "mass",
  "small batch"). In both cases output a reasonable concrete expanded list,
  grounded in the observation and in what makes sense for a single scheduler
  cycle. If the step mentions the same entity more than once, include all
  requested occurrences in their intended order.
* Do NOT skip a requested entity just because the step says it happens "after",
  "when", "once", or "if" another prerequisite is ready. Output the requested
  entity anyway; the downstream scheduler will wait for prerequisites.
* Output only exact names from the Canonical Units / Upgrades lists below;
  if you cannot confidently map a request to one of those names, omit it.
* Do NOT output action/ability names such as TERRANBUILD_BARRACKS or
  BARRACKSTRAIN_MARINE. Output entity names such as Barracks or Marine.
* Upgrades / researches should appear at most once per cycle.
* For add-ons, use the host-specific canonical name, e.g. BarracksTechLab,
  not generic TechLab.

[Name Hints: Jargon and Upgrade Categories]
These hints help interpret strategy language. They do not expand the legal
output names. Every output name must still exactly match one name in the
Canonical Units or Canonical Upgrades lists below.

Common jargon:
- rax -> Barracks
- ebay -> EngineeringBay
- cc -> CommandCenter
- depot -> SupplyDepot
- mule economy -> OrbitalCommand
- blue flame -> HighCapacityBarrels
- stim -> Stimpack
- combat shield -> ShieldWall
- concussive shells -> PunisherGrenades
- yamato -> BattlecruiserEnableSpecializations
- advanced ballistics -> LiberatorAGRangeUpgrade
- building armor -> TerranBuildingArmor
- bio -> usually Marine, Marauder, Medivac, plus infantry upgrades when
  explicitly requested.
- mech -> usually Factory units and vehicle upgrades when explicitly requested.
- sky Terran -> usually Starport units and ship upgrades when explicitly
  requested.

Do not output a whole composition from a general term alone. Use general terms
only to interpret concrete requests in the Strategy Step.

Upgrade categories:
- Infantry upgrades: Stimpack, ShieldWall, PunisherGrenades,
  TerranInfantryWeaponsLevel1/2/3, TerranInfantryArmorsLevel1/2/3. These
  improve Marine/Marauder bio timing, durability, and damage.
- Vehicle/mech upgrades: TerranVehicleWeaponsLevel1/2/3,
  TerranVehicleArmorsLevel1/2/3, SmartServos, DrillClaws, HighCapacityBarrels,
  Cyclone upgrades. These support Factory-based mech armies and unit-specific
  power spikes.
- Air/ship upgrades: TerranShipWeaponsLevel1/2/3,
  TerranShipArmorsLevel1/2/3, BansheeCloak, BansheeSpeed,
  LiberatorAGRangeUpgrade, BattlecruiserEnableSpecializations. These improve
  Starport units, air control, harassment, and late-game air tech.
- Shared vehicle/ship upgrades: TerranVehicleAndShipWeaponsLevel1/2/3,
  TerranVehicleAndShipArmorsLevel1/2/3. These are broad Armory upgrades for
  mixed mech and air armies.
- Building/defensive upgrades: HiSecAutoTracking, TerranBuildingArmor,
  NeosteelFrame. These improve static defense, building durability, or Terran
  structure utility.
- Specialist tech upgrades: PersonalCloaking, RavenCorvidReactor,
  RavenEnhancedMunitions, RavenRecalibratedExplosives, Medivac upgrades. These
  unlock or improve spellcaster, support, and utility behavior.

[Canonical {race_cap} Units]
{units_text}

[Canonical {race_cap} Upgrades]
{upgrades_text}

Output ONLY one JSON object, no prose, no markdown fences. Do not use counts.
Repeat a name when multiple copies are needed:
{{"ordered_names":["SupplyDepot","Barracks","BarracksTechLab","Marine","Marine","Marine"]}}"""

    user_msg = f"[Current Observation]\n{obs_text or '(empty)'}\n\n[Strategy Step]\n{plan_text}"

    return [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def parse_ordered_naming_response(text: str) -> Optional[List[str]]:
    """Parse ``{"ordered_names": [...]}`` into a flat name list."""
    if not text:
        return None
    data = _extract_json_object(text)
    if data is None:
        logger.warning("Ordered Naming Agent output is not valid JSON: %r", text[:200])
        return None
    raw = data.get("ordered_names")
    if not isinstance(raw, list):
        return None
    names = [name.strip() for name in raw if isinstance(name, str) and name.strip()]
    return names
