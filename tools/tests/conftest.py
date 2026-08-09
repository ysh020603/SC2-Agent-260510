"""Make bundled python-sc2 importable and provide human-skill fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BUNDLED_PYTHON_SC2 = REPOSITORY_ROOT / "python-sc2"

for path in (REPOSITORY_ROOT, BUNDLED_PYTHON_SC2):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)


@pytest.fixture
def fixture_skill_root():
    return Path(__file__).parent / "fixtures" / "readable_skills"


@pytest.fixture
def api_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "llm_agents_pool": {
                    "DeepSeek-V4-flash": {
                        "model_name": "deepseek-v4-flash",
                        "api_key": "fixture",
                        "api_url": "https://fixture.invalid/v1",
                        "is_reasoning": False,
                    },
                    "DeepSeek-V4-flash_think": {
                        "model_name": "deepseek-v4-flash",
                        "api_key": "fixture",
                        "api_url": "https://fixture.invalid/v1",
                        "is_reasoning": True,
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    return path
