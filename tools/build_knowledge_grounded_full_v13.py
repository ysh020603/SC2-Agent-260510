from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path


SOURCE_METHOD = "full_signed_graph"
OUTPUT_METHOD = "full_knowledge_grounded_graph_v13"


def resolve_destination(repo_root: Path, destination_root: Path | None = None) -> Path:
    """Resolve the skill path used by the runtime's ``../SKILL_MINING_V2_READABLE``."""
    skill_root = destination_root or (repo_root.parent / "SKILL_MINING_V2_READABLE")
    return skill_root.resolve() / OUTPUT_METHOD


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument(
        "--destination-root",
        type=Path,
        help="Runtime SKILL_MINING_V2_READABLE root (defaults to the agent repo's parent).",
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    source = args.source_root.resolve() / SOURCE_METHOD
    destination = resolve_destination(repo_root, args.destination_root)
    if not source.is_dir():
        raise FileNotFoundError(source)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing method: {destination}")

    rows = []
    for marker in sorted(source.glob("*/*/*/SKILL.md")):
        relative = marker.parent.relative_to(source)
        target = destination / relative
        shutil.copytree(marker.parent, target)
        index_path = target / "index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        index["method"] = OUTPUT_METHOD
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        skill_path = target / "SKILL.md"
        skill_text = re.sub(
            r"(?m)^- Method:.*$", "- Method: Knowledge-Grounded Full V13", skill_path.read_text(encoding="utf-8")
        )
        skill_path.write_text(skill_text, encoding="utf-8")
        rows.append({"skill_id": marker.parent.name, "path": str(relative)})

    manifest = {
        "schema_version": 1, "method": OUTPUT_METHOD, "source_method": SOURCE_METHOD,
        "source_root": str(source), "skills": len(rows), "rows": rows,
        "design": "human trajectory signs + node routing + positive/negative experience + validated SC2 knowledge + general process feedback",
    }
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "BUILD_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({"method": OUTPUT_METHOD, "skills": len(rows)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
