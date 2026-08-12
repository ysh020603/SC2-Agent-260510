"""Build an opening-conditioned ensemble from completed 60-game versions."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


DEFAULT_SOURCE = "full_branch_faithful_graph_v7"
SOURCE_BY_OPENING = {
    "PvP_O01": "full_race_hybrid_graph_v6",
    "TvP_O02": "full_failure_aware_graph_v4",
    "TvT_O03": "full_failure_aware_graph_v4",
    "TvZ_O01": "full_failure_aware_graph_v4",
}
OUTPUT_METHOD = "full_opening_champion_graph_v10"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    readable = repo_root / "SKILL_MINING_V2_READABLE"
    output_root = readable / OUTPUT_METHOD
    rows = []
    default_root = readable / DEFAULT_SOURCE
    for marker in sorted(default_root.glob("*/*/*/SKILL.md")):
        opening_id = marker.parent.name
        source_method = SOURCE_BY_OPENING.get(opening_id, DEFAULT_SOURCE)
        relative = marker.parent.relative_to(default_root)
        source = readable / source_method / relative
        destination = output_root / relative
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
        index_path = destination / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index["method"] = OUTPUT_METHOD
        write_json(index_path, index)
        root_path = destination / "SKILL.md"
        root_text = root_path.read_text(encoding="utf-8")
        root_text = __import__("re").sub(r"(?m)^- Method:.*$", "- Method: Opening-Champion Full V10", root_text)
        root_path.write_text(root_text, encoding="utf-8")
        provenance = destination / "provenance"
        provenance.mkdir(exist_ok=True)
        write_json(provenance / "opening_champion_selection.json", {
            "schema_version": 1,
            "method": OUTPUT_METHOD,
            "opening_id": opening_id,
            "source_method": source_method,
            "selection_basis": "completed DeepSeek Flash MediumHard 60-game version reports",
            "agent_visible": False,
        })
        rows.append({"opening_id": opening_id, "source_method": source_method})
    summary = {"schema_version": 1, "method": OUTPUT_METHOD, "skills": len(rows), "sources": rows}
    write_json(repo_root / "analysis/outputs_readable_skill_v1/15_full_opening_champion_v10/summary.json", summary)
    print(json.dumps({"method": OUTPUT_METHOD, "skills": len(rows)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
