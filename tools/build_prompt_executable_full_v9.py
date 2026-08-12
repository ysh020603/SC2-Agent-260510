"""Copy the V7 branch-faithful graph for prompt-only executability integration."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


BASE_METHOD = "full_branch_faithful_graph_v7"
OUTPUT_METHOD = "full_prompt_executable_graph_v9"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    base_root = repo_root / "SKILL_MINING_V2_READABLE" / BASE_METHOD
    output_root = repo_root / "SKILL_MINING_V2_READABLE" / OUTPUT_METHOD
    rows = []
    for source in sorted(base_root.glob("*/*/*/SKILL.md")):
        source_dir = source.parent
        opening_id = source_dir.name
        destination = output_root / source_dir.relative_to(base_root)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source_dir, destination)
        index_path = destination / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index["method"] = OUTPUT_METHOD
        write_json(index_path, index)
        skill_path = destination / "SKILL.md"
        skill_path.write_text(
            skill_path.read_text(encoding="utf-8").replace(
                "- Method: Branch-Faithful Full V7", "- Method: Prompt-Executable Full V9"
            ),
            encoding="utf-8",
        )
        provenance = destination / "provenance"
        provenance.mkdir(exist_ok=True)
        write_json(provenance / "prompt_executable_integration.json", {
            "schema_version": 1,
            "method": OUTPUT_METHOD,
            "opening_id": opening_id,
            "base_method": BASE_METHOD,
            "agent_visible": True,
            "integration": "single-pass prompt planning; no variant runtime rejection",
        })
        rows.append(opening_id)
    summary = {"schema_version": 1, "method": OUTPUT_METHOD, "base_method": BASE_METHOD, "skills": len(rows)}
    write_json(repo_root / "analysis/outputs_readable_skill_v1/14_full_prompt_executable_v9/summary.json", summary)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
