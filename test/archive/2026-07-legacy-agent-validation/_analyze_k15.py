"""Summarize k15 15x3 matrix results and flag anomalies."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "game_records" / "k15"

MAPS = ["KairosJunctionLE", "AutomatonLE", "AbyssalReefLE"]
ENEMY_RACES = ["terran", "protoss", "zerg"]
STRATEGIES = [
    ("terran", "marine_rush"),
    ("terran", "bio"),
    ("terran", "blueflame_locks"),
    ("terran", "two_base_matrix_tanks"),
    ("terran", "yamato_rust_fleet"),
    ("protoss", "four_gate"),
    ("protoss", "dark_templar_rush"),
    ("protoss", "robo"),
    ("protoss", "voidray"),
    ("protoss", "macro_stalkers"),
    ("zerg", "twelve_pool"),
    ("zerg", "macro_roach"),
    ("zerg", "roach_hydra"),
    ("zerg", "lurkers"),
    ("zerg", "mutalisk"),
]


def build_jobs():
    jobs = []
    idx = 0
    for bot_race, strategy in STRATEGIES:
        for enemy_race in ENEMY_RACES:
            jobs.append(
                {
                    "index": idx,
                    "bot_race": bot_race,
                    "strategy": strategy,
                    "enemy_race": enemy_race,
                    "map_name": MAPS[idx % 3],
                }
            )
            idx += 1
    return jobs


def latest_valid(run_index: int):
    best = None
    if not BATCH.is_dir():
        return None
    for p in BATCH.iterdir():
        if not p.is_dir() or not p.name.endswith(f"_run{run_index}"):
            continue
        for j in p.glob("*.json"):
            if j.name.endswith(".llm_calls.json"):
                continue
            try:
                d = json.loads(j.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(d, dict) and "metadata" in d:
                if best is None or j.stat().st_mtime >= best[0]:
                    best = (j.stat().st_mtime, p, j, d)
    return best


def walk_drops(obj, unknown: Counter, unmapped: Counter):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "dropped_unknown_names" and isinstance(v, list):
                for item in v:
                    unknown[str(item)] += 1
            elif k == "dropped_unmapped_names" and isinstance(v, list):
                for item in v:
                    unmapped[str(item)] += 1
            else:
                walk_drops(v, unknown, unmapped)
    elif isinstance(obj, list):
        for x in obj:
            walk_drops(x, unknown, unmapped)


def log_stats(match_dir: Path):
    abandoned = Counter()
    cant_place = Counter()
    err_flags = set()
    for lp in match_dir.glob("*.log"):
        text = lp.read_text(encoding="utf-8", errors="ignore")
        if "Traceback" in text:
            err_flags.add("Traceback")
        if re.search(r"\bERROR\b", text):
            err_flags.add("ERROR")
        if "engine rejected" in text.lower():
            err_flags.add("engine_rejected")
        if "No module named" in text:
            err_flags.add("No module named")
        for m in re.finditer(r"Abandoned stuck RUNNING action ([A-Z0-9_]+)", text):
            abandoned[m.group(1)] += 1
        for m in re.finditer(r"Can't find free position to build ([A-Z0-9_]+)", text):
            cant_place[m.group(1)] += 1
    return abandoned, cant_place, err_flags


def main() -> None:
    jobs = build_jobs()
    rows = []
    results = Counter()
    missing = []
    issue_rows = []
    by_strategy = defaultdict(list)
    all_unknown = Counter()
    all_cant = Counter()
    all_abd = Counter()

    for meta in jobs:
        item = latest_valid(meta["index"])
        if item is None:
            missing.append(meta)
            rows.append({**meta, "ok": False})
            continue
        _, p, _jpath, d = item
        unknown, unmapped = Counter(), Counter()
        walk_drops(d, unknown, unmapped)
        abandoned, cant_place, err_flags = log_stats(p)
        result = d["metadata"].get("result")
        results[str(result)] += 1
        row = {
            **meta,
            "ok": True,
            "dir": p.name,
            "result": result,
            "duration": d["metadata"].get("game_duration_formatted"),
            "cycles": len(d.get("interactions") or []),
            "unknown": dict(unknown),
            "unmapped": dict(unmapped),
            "unknown_n": sum(unknown.values()),
            "unmapped_n": sum(unmapped.values()),
            "abandoned": dict(abandoned),
            "abandoned_n": sum(abandoned.values()),
            "cant_place": dict(cant_place),
            "cant_place_n": sum(cant_place.values()),
            "err_flags": sorted(err_flags),
        }
        rows.append(row)
        by_strategy[f"{meta['bot_race']}/{meta['strategy']}"].append(row)
        all_unknown.update(unknown)
        all_cant.update(cant_place)
        all_abd.update(abandoned)
        if (
            row["unknown_n"]
            or row["unmapped_n"]
            or row["abandoned_n"]
            or row["cant_place_n"]
            or row["err_flags"]
        ):
            issue_rows.append(row)

    print(f"completed={sum(1 for r in rows if r.get('ok'))}/45 missing={len(missing)}")
    print(f"results={dict(results)}")
    print("\n=== BY STRATEGY ===")
    for key in sorted(by_strategy):
        parts = []
        for r in by_strategy[key]:
            parts.append(
                f"{r['enemy_race'][0].upper()}:{r['result']}/{r['duration']}"
                f"(u{r['unknown_n']}a{r['abandoned_n']}p{r['cant_place_n']})"
            )
        print(f"{key}: " + " | ".join(parts))

    print(f"\n=== ISSUES ({len(issue_rows)}) ===")
    for r in issue_rows:
        print(
            f"run{r['index']:02d} {r['bot_race']}/{r['strategy']} vs {r['enemy_race']} "
            f"@ {r['map_name']} => {r['result']} {r['duration']}"
        )
        if r["unknown"]:
            print(f"  unknown={r['unknown']}")
        if r["unmapped"]:
            print(f"  unmapped={r['unmapped']}")
        if r["abandoned"]:
            print(f"  abandoned={r['abandoned']}")
        if r["cant_place"]:
            top = sorted(r["cant_place"].items(), key=lambda kv: -kv[1])[:8]
            print(f"  cant_place_top={top}")
        if r["err_flags"]:
            print(f"  err_flags={r['err_flags']}")

    if missing:
        print("\n=== MISSING ===")
        for m in missing:
            print(m)

    print("\n=== GLOBAL UNKNOWN ===", dict(all_unknown))
    print("=== GLOBAL ABANDON TOP ===", all_abd.most_common(15))
    print("=== GLOBAL CANT_PLACE TOP ===", all_cant.most_common(15))

    out_path = BATCH / "runner_logs" / "analysis_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
