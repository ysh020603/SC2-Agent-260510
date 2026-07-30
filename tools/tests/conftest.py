"""Make the repository's bundled python-sc2 importable in documented tests."""

from __future__ import annotations

import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BUNDLED_PYTHON_SC2 = REPOSITORY_ROOT / "python-sc2"

for path in (REPOSITORY_ROOT, BUNDLED_PYTHON_SC2):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)
