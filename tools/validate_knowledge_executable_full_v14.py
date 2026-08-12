from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from SC2_Agent.human_skill_common.skill_loader import ReadableSkillLoader
from tools.build_knowledge_executable_full_v14 import OUTPUT_METHOD, POLICY_METHOD


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.skill_root.resolve()
    method_root = root / OUTPUT_METHOD
    manifest = json.loads((method_root / "BUILD_MANIFEST.json").read_text(encoding="utf-8"))
    loader = ReadableSkillLoader(str(root))
    failures: list[str] = []
    scores: list[float] = []
    negative_nodes = 0
    overlay_nodes = 0

    for row in manifest.get("rows") or []:
        relative = Path(row["path"])
        race, matchup, skill_id = relative.parts
        target_dir = method_root / relative
        policy_dir = root / POLICY_METHOD / relative
        target_index = json.loads((target_dir / "index.json").read_text(encoding="utf-8"))
        policy_index = json.loads((policy_dir / "index.json").read_text(encoding="utf-8"))
        for node_id, policy_node in policy_index["nodes"].items():
            target_node = target_index["nodes"].get(node_id)
            if target_node is None:
                failures.append(f"{skill_id}/{node_id}: executable policy node missing")
                continue
            for key, value in policy_node.items():
                if key == "children":
                    if target_node.get(key, [])[: len(value)] != value:
                        failures.append(f"{skill_id}/{node_id}: original policy transitions changed")
                elif target_node.get(key) != value:
                    failures.append(f"{skill_id}/{node_id}: policy field {key} changed")
        try:
            loader.load(
                method=OUTPUT_METHOD,
                race=race,
                matchup=matchup,
                skill_id=skill_id,
                allowed_node_types={"positive", "negative", "default"},
                allow_graph_navigation=True,
            )
        except Exception as exc:
            failures.append(f"{skill_id}: loader validation failed: {exc}")
        for alignment in row.get("alignments") or []:
            scores.append(float(alignment.get("score") or 0))
            node_id = alignment["policy_node"]
            target_text = (target_dir / target_index["nodes"][node_id]["path"]).read_text(encoding="utf-8")
            policy_text = (policy_dir / policy_index["nodes"][node_id]["path"]).read_text(encoding="utf-8")
            if policy_text.split("## Possible Next Situations", 1)[0].strip() not in target_text:
                failures.append(f"{skill_id}/{node_id}: executable policy body not preserved")
            if "## Knowledge Constraint Overlay" not in target_text:
                failures.append(f"{skill_id}/{node_id}: missing knowledge overlay")
            else:
                overlay_nodes += 1
            if target_index["nodes"][node_id].get("type") == "negative":
                negative_nodes += 1
        for route in row.get("negative_routes") or []:
            negative_id = route["negative_node"]
            negative_node = target_index["nodes"].get(negative_id) or {}
            if negative_node.get("type") != "negative":
                failures.append(f"{skill_id}/{negative_id}: routed negative identity missing")
            else:
                negative_nodes += 1
            parent = target_index["nodes"].get(route["routed_from"]) or {}
            if negative_id not in (parent.get("children") or []):
                failures.append(f"{skill_id}/{negative_id}: negative route not linked")
            negative_text = (target_dir / negative_node.get("path", "missing")).read_text(encoding="utf-8")
            if "## Routing Boundary" not in negative_text or "Never reproduce" not in negative_text:
                failures.append(f"{skill_id}/{negative_id}: negative execution boundary missing")

    summary = {
        "valid": not failures,
        "method": OUTPUT_METHOD,
        "skills": len(manifest.get("rows") or []),
        "nodes": len(scores),
        "overlay_nodes": overlay_nodes,
        "negative_nodes": negative_nodes,
        "alignment_score": {
            "min": round(min(scores), 6) if scores else 0,
            "mean": round(sum(scores) / len(scores), 6) if scores else 0,
            "max": round(max(scores), 6) if scores else 0,
        },
        "failures": failures,
    }
    output = method_root / "VALIDATION_SUMMARY.json"
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if summary["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
