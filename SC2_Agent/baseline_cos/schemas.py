"""Parsers for CoS L1 / L2 artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .decision_prompt import MacroDecision, _extract_json_object, parse_decision_response

COS_HISTORY_SIZE = 5
L1_FIELDS = (
    "game_time",
    "economy",
    "production",
    "army",
    "enemy",
    "supply",
    "committed_work",
    "strategic_signal",
)


@dataclass(frozen=True)
class L1Summary:
    game_time: float
    economy: str
    production: str
    army: str
    enemy: str
    supply: str
    committed_work: str
    strategic_signal: str


def parse_l1_response(text: str) -> Optional[L1Summary]:
    data = _extract_json_object(text)
    if data is None:
        return None
    values: Dict[str, Any] = {}
    for field in L1_FIELDS:
        if field not in data:
            return None
        values[field] = data[field]
    game_time = values["game_time"]
    if isinstance(game_time, bool) or not isinstance(game_time, (int, float)):
        return None
    for field in L1_FIELDS[1:]:
        if not isinstance(values[field], str) or not values[field].strip():
            return None
    return L1Summary(
        game_time=float(game_time),
        economy=values["economy"].strip()[:1000],
        production=values["production"].strip()[:1000],
        army=values["army"].strip()[:1000],
        enemy=values["enemy"].strip()[:1000],
        supply=values["supply"].strip()[:1000],
        committed_work=values["committed_work"].strip()[:1000],
        strategic_signal=values["strategic_signal"].strip()[:1000],
    )


def l1_to_dict(item: L1Summary) -> Dict[str, Any]:
    return {
        "game_time": item.game_time,
        "economy": item.economy,
        "production": item.production,
        "army": item.army,
        "enemy": item.enemy,
        "supply": item.supply,
        "committed_work": item.committed_work,
        "strategic_signal": item.strategic_signal,
    }


def decision_to_dict(decision: MacroDecision) -> Dict[str, Any]:
    return {"reason": decision.reason, "ordered_names": list(decision.ordered_names)}


__all__ = [
    "COS_HISTORY_SIZE",
    "L1_FIELDS",
    "L1Summary",
    "MacroDecision",
    "parse_l1_response",
    "parse_decision_response",
    "l1_to_dict",
    "decision_to_dict",
]
