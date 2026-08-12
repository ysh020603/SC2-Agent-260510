import collections
import glob
import json
import os
import sys

from SC2_Agent.human_skill_full_v8.guard import prerequisite_error, race_macro_error


report = json.load(open(sys.argv[1], encoding="utf-8"))
method = sys.argv[2]
totals = collections.Counter()
by_race = collections.defaultdict(collections.Counter)
examples = {}
for row in report["rows"]:
    if row.get("method") != method or not row.get("valid_artifact"):
        continue
    race = {"P": "protoss", "T": "terran", "Z": "zerg"}[row["skill_id"][0]]
    human_path = glob.glob(os.path.join(row["record_dir"], "*.human_skill.json"))[0]
    for decision in json.load(open(human_path, encoding="utf-8")).get("decisions", []):
        ordered = ((decision.get("decision") or {}).get("ordered_names") or [])
        if not ordered:
            continue
        totals["decisions"] += 1
        by_race[race]["decisions"] += 1
        error = race_macro_error(
            race=race,
            obs_text=decision.get("observation_at_this_moment") or "",
            ordered_names=ordered,
            game_time_seconds=float(decision.get("game_time") or 0),
        ) or prerequisite_error(
            race=race,
            obs_text=decision.get("observation_at_this_moment") or "",
            ordered_names=ordered,
        )
        if not error:
            totals["accepted"] += 1
            by_race[race]["accepted"] += 1
            continue
        if error.startswith("V8 Zerg executable repair"):
            category = "V8 Zerg executable repair"
        elif error.startswith("V8 Terran executable repair"):
            category = "V8 Terran executable repair"
        elif error.startswith("V8 prerequisite repair"):
            category = "V8 prerequisite repair"
        else:
            category = error.split(":", 1)[0]
        totals[category] += 1
        by_race[race][category] += 1
        examples.setdefault((race, category), {
            "skill": row["skill_id"], "run": row["run_index"],
            "time": decision.get("game_time"), "error": error, "ordered": ordered,
        })
print(json.dumps({"totals": totals, "by_race": by_race, "examples": list(examples.values())}, ensure_ascii=False, indent=2))
