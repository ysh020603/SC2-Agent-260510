"""Backward-compatible access to the shared universal tactical plan.

New Human Skill agents call the universal plan through their bot superclass.
This module remains only for callers that imported the early runtime skeleton.
"""

from __future__ import annotations

from sc2.data import Race

from sharpy.plans import BuildOrder

from SC2_Agent.universal_tactics import create_universal_tactical_plan


def make_terran_generic_tools() -> BuildOrder:
    """Return the same state-driven V1 plan used by every Skill variant."""
    return create_universal_tactical_plan(Race.Terran)


__all__ = ["make_terran_generic_tools"]
