"""Validation helpers used by tests and experiment launchers."""

from __future__ import annotations

from dataclasses import replace

from .config import DEFAULT_CONFIG
from .controller import UniversalTacticalController


ROUTING_DIMENSIONS = ("skill_id", "opening_id", "ablation_method")


def config_fingerprint(config=DEFAULT_CONFIG):
    return config.stable_hash()


def cross_context_postures(snapshot, contexts):
    """Context labels are deliberately ignored; only the snapshot is routed."""
    return [UniversalTacticalController().decide_posture(replace(snapshot)) for _context in contexts]


def assert_cross_context_invariance(snapshot, contexts):
    postures = cross_context_postures(snapshot, contexts)
    if len(set(postures)) != 1:
        raise AssertionError("tactical posture changed across skill/opening/ablation context")
    return postures[0]
