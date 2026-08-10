"""Load and validate the python-sc2 snapshot bundled with this Agent."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType


AGENT_ROOT = Path(__file__).resolve().parent
BUNDLED_PYTHON_SC2 = AGENT_ROOT / "python-sc2"

# These mappings distinguish the bundled snapshot from the older burnysc2
# package previously imported from the SC2_0615 conda environment.
REQUIRED_UPGRADE_MAPPINGS = (
    "ARMORPIERCINGROCKETS",
    "CYCLONELOCKONRANGEUPGRADE",
    "CYCLONERAPIDFIRELAUNCHERS",
    "DURABLEMATERIALS",
    "MEDIVACINCREASESPEEDBOOST",
    "MEDIVACRAPIDDEPLOYMENT",
    "NEOSTEELFRAME",
    "RAVENCORVIDREACTOR",
    "RAVENENHANCEDMUNITIONS",
    "RAVENRECALIBRATEDEXPLOSIVES",
    "TERRANSHIPARMORSLEVEL1",
    "TERRANSHIPARMORSLEVEL2",
    "TERRANSHIPARMORSLEVEL3",
    "TERRANVEHICLEARMORSLEVEL1",
    "TRANSFORMATIONSERVOS",
)


def _is_inside(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def _validate_origin(sc2_module: ModuleType) -> Path:
    module_file = getattr(sc2_module, "__file__", None)
    if not module_file:
        raise RuntimeError("Imported sc2 module has no __file__; cannot verify its source")
    origin = Path(module_file).resolve()
    if not _is_inside(origin, BUNDLED_PYTHON_SC2):
        raise RuntimeError(
            "python-sc2 was imported before the Agent runtime bootstrap. "
            f"Expected a module under {BUNDLED_PYTHON_SC2}, got {origin}."
        )
    return origin


def ensure_bundled_python_sc2() -> Path:
    """Prepend the bundled dependency, import it, and verify compatibility."""
    package_dir = BUNDLED_PYTHON_SC2 / "sc2"
    if not package_dir.is_dir():
        raise RuntimeError(
            "Bundled python-sc2 is missing. The Agent repository must contain "
            f"{BUNDLED_PYTHON_SC2}."
        )

    bundled_path = str(BUNDLED_PYTHON_SC2)
    sys.path[:] = [entry for entry in sys.path if entry != bundled_path]
    sys.path.insert(0, bundled_path)

    sc2_module = importlib.import_module("sc2")
    origin = _validate_origin(sc2_module)

    from sc2.dicts.upgrade_researched_from import UPGRADE_RESEARCHED_FROM
    from sc2.ids.upgrade_id import UpgradeId

    missing = [
        name
        for name in REQUIRED_UPGRADE_MAPPINGS
        if UpgradeId.__members__.get(name) not in UPGRADE_RESEARCHED_FROM
    ]
    if missing:
        raise RuntimeError(
            f"Bundled python-sc2 at {origin} is incompatible; missing upgrade mappings: "
            + ", ".join(missing)
        )
    return origin


__all__ = [
    "AGENT_ROOT",
    "BUNDLED_PYTHON_SC2",
    "REQUIRED_UPGRADE_MAPPINGS",
    "ensure_bundled_python_sc2",
]
