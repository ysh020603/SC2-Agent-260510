"""Configuration and content guards for readable-skill experiments."""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable

from API_Tools.llm_caller import load_agent_pool


class HumanSkillValidationError(ValueError):
    pass


def resolve_api_config(repo_root: str, explicit: str = "") -> str:
    candidates = [
        explicit,
        os.environ.get("HUMAN_SKILL_API_CONFIG", ""),
        os.path.join(repo_root, "API_config", "config.json"),
        os.path.join(os.path.dirname(repo_root), "API_config", "config.json"),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(os.path.abspath(candidate)):
            return os.path.abspath(candidate)
    raise FileNotFoundError("No API config found. Set HUMAN_SKILL_API_CONFIG or pass api_config_path.")


def require_non_reasoning_model(model_key: str, config_path: str) -> Dict[str, Any]:
    key = str(model_key or "").strip()
    if not key:
        raise HumanSkillValidationError("decision model key is required")
    if "think" in key.lower():
        raise HumanSkillValidationError(f"thinking model keys are forbidden: {key}")
    pool = load_agent_pool(config_path=config_path, force_reload=True).get("llm_agents_pool") or {}
    cfg = pool.get(key)
    if not isinstance(cfg, dict):
        raise HumanSkillValidationError(f"model key is absent from config: {key}")
    if cfg.get("is_reasoning") is not False:
        raise HumanSkillValidationError(f"human-skill experiments require is_reasoning=false: {key}")
    return cfg


def validate_node_type(node_type: str, allowed: Iterable[str]) -> None:
    if node_type.lower() not in {value.lower() for value in allowed}:
        raise HumanSkillValidationError(f"node type {node_type!r} is not allowed for this agent")


def validate_relative_node_path(path: str) -> str:
    normalized = str(path or "").replace("\\", "/")
    if not normalized.startswith("nodes/"):
        raise HumanSkillValidationError(f"node path must stay under nodes/: {path!r}")
    if normalized.startswith("/") or ".." in normalized.split("/"):
        raise HumanSkillValidationError(f"unsafe node path: {path!r}")
    return normalized
