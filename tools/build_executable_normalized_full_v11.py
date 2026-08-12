"""Copy V10 knowledge for deterministic early queue normalization."""
from __future__ import annotations
import argparse, json, shutil
from pathlib import Path

BASE_METHOD = "full_opening_champion_graph_v10"
OUTPUT_METHOD = "full_executable_normalized_graph_v11"

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--repo-root", type=Path, required=True)
    root = parser.parse_args().repo_root.resolve(); readable = root / "SKILL_MINING_V2_READABLE"
    rows = []
    for marker in sorted((readable / BASE_METHOD).glob("*/*/*/SKILL.md")):
        rel = marker.parent.relative_to(readable / BASE_METHOD); dst = readable / OUTPUT_METHOD / rel
        if dst.exists(): shutil.rmtree(dst)
        shutil.copytree(marker.parent, dst)
        index_path = dst / "index.json"; index = json.loads(index_path.read_text(encoding="utf-8")); index["method"] = OUTPUT_METHOD
        index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        skill_path = dst / "SKILL.md"; import re
        skill_path.write_text(re.sub(r"(?m)^- Method:.*$", "- Method: Executable-Normalized Full V11", skill_path.read_text(encoding="utf-8")), encoding="utf-8")
        provenance = dst / "provenance"; provenance.mkdir(exist_ok=True)
        (provenance / "executable_normalization.json").write_text(json.dumps({"schema_version":1,"method":OUTPUT_METHOD,"base_method":BASE_METHOD,"opening_id":marker.parent.name,"agent_visible":False,"normalization":["zerg_low_army_larva_to_combat","terran_low_army_bank_to_production"]}, indent=2), encoding="utf-8")
        rows.append(marker.parent.name)
    print(json.dumps({"method":OUTPUT_METHOD,"skills":len(rows)}, sort_keys=True)); return 0

if __name__ == "__main__": raise SystemExit(main())
