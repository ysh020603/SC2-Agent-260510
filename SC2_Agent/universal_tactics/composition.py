"""Composition summaries derived from Sharpy's ExtendedPower values."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from sharpy.general.extended_power import ExtendedPower, siege


@dataclass(frozen=True)
class CompositionProfile:
    total_power: float
    ground_fraction: float
    air_fraction: float
    anti_ground_coverage: float
    anti_air_coverage: float
    melee_fraction: float
    siege_fraction: float
    detector_present: bool
    stealth_present: bool
    average_speed: Optional[float] = None
    average_range: Optional[float] = None


def _fraction(value: float, total: float) -> float:
    return max(0.0, float(value)) / max(float(total), 1e-9)


def siege_power_from_units(units: Iterable, unit_values) -> float:
    """Accumulate siege power explicitly; ExtendedPower historically overwrote it."""
    result = 0.0
    for unit in units:
        if getattr(unit, "type_id", None) in siege:
            result += float(unit_values.power(unit))
    return result


def profile_from_power(
    power: ExtendedPower,
    *,
    explicit_siege_power: Optional[float] = None,
) -> CompositionProfile:
    total = max(0.0, float(power.power))
    siege_power = power.siege_power if explicit_siege_power is None else explicit_siege_power
    return CompositionProfile(
        total_power=total,
        ground_fraction=_fraction(power.ground_presence, total),
        air_fraction=_fraction(power.air_presence, total),
        anti_ground_coverage=_fraction(power.ground_power, total),
        anti_air_coverage=_fraction(power.air_power, total),
        melee_fraction=_fraction(power.melee_power, total),
        siege_fraction=_fraction(siege_power, total),
        detector_present=bool(power.detectors),
        stealth_present=power.stealth_power > 0,
    )
