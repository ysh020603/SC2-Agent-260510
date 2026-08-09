"""Auditable variant-to-package and variant-to-method binding."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any, Type

from .agent_base import HumanSkillAgent


@dataclass(frozen=True)
class VariantSpec:
    cli_name: str
    package: str
    method: str


VARIANTS = {
    "human-skill-full": VariantSpec("human-skill-full", "SC2_Agent.human_skill_full", "full_signed_graph"),
    "human-skill-single-trace": VariantSpec(
        "human-skill-single-trace", "SC2_Agent.human_skill_single_trace", "ablation_single_trace"
    ),
    "human-skill-static-population": VariantSpec(
        "human-skill-static-population", "SC2_Agent.human_skill_static_population", "ablation_static_population"
    ),
    "human-skill-flat-adaptive": VariantSpec(
        "human-skill-flat-adaptive", "SC2_Agent.human_skill_flat_adaptive", "ablation_flat_adaptive"
    ),
    "human-skill-positive-only": VariantSpec(
        "human-skill-positive-only", "SC2_Agent.human_skill_positive_only", "ablation_positive_only"
    ),
    "human-skill-frequency-only": VariantSpec(
        "human-skill-frequency-only", "SC2_Agent.human_skill_frequency_only", "ablation_frequency_only"
    ),
}


def require_variant(name: str) -> VariantSpec:
    normalized = str(name or "").strip().lower()
    try:
        return VARIANTS[normalized]
    except KeyError as exc:
        raise ValueError(f"unknown human-skill agent {name!r}; expected {sorted(VARIANTS)}") from exc


def load_variant_package(name: str) -> tuple[VariantSpec, Any, Type[HumanSkillAgent]]:
    spec = require_variant(name)
    package = importlib.import_module(spec.package)
    if package.SKILL_METHOD != spec.method:
        raise RuntimeError(f"variant package method mismatch: {spec.package}")
    return spec, package, package.Agent
