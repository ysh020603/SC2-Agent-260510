"""Enabled representative strategy registry.

Non-representative strategy directories stay in the repository for later
curation, but are intentionally unreachable through the production runner.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from SC2_Agent.data_tools.race_catalog import normalize_race


_SKILL_ROOT = Path(__file__).resolve().parents[1] / "SKILL"


@lru_cache(maxsize=3)
def enabled_strategy_names(race: str) -> tuple[str, ...]:
    race = normalize_race(race)
    path = _SKILL_ROOT / race / "registry.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    names = data.get("registered_strategies")
    if not isinstance(names, list) or not names:
        raise ValueError(f"No enabled strategies configured in {path}")
    normalized = tuple(str(name).strip() for name in names)
    if any(not name for name in normalized) or len(set(normalized)) != len(normalized):
        raise ValueError(f"Invalid enabled strategy registry: {path}")
    return normalized


def require_enabled_strategy(race: str, strategy: str) -> str:
    race = normalize_race(race)
    strategy = str(strategy or "").strip()
    enabled = enabled_strategy_names(race)
    if strategy not in enabled:
        raise ValueError(
            f"Strategy '{strategy}' is disabled for {race}. "
            f"Enabled representative strategies: {', '.join(enabled)}"
        )
    return strategy


__all__ = ["enabled_strategy_names", "require_enabled_strategy"]
