"""Analyze kn30 full-matrix records for anomaly logging. No agent code changes."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH = ROOT / "game_records" / "kn30"

JOBS = {
    0: ("terran", "marine_rush", "KairosJunctionLE"),
    1: ("terran", "bio", "AutomatonLE"),
    2: ("terran", "two_base_matrix_tanks", "AbyssalReefLE"),
    3: ("protoss", "four_gate", "AutomatonLE"),
    4: ("protoss", "voidray", "AbyssalReefLE"),
    5: ("zerg", "lings", "KairosJunctionLE"),
    6: ("zerg", "roach_hydra", "AutomatonLE"),
}

PATTERNS = [
    "Traceback",
    r"\bERROR\b",
    "engine rejected",
    "issue failed",
    "No module named",
    "Abandoned stuck RUNNING",
    "Can't find free position",
]


def latest_valid(idx: int):
    best = None
    for p in BATCH.iterdir():
        if not p.is_dir() or not p.name.endswith(f"_run{idx}"):
            continue
        for j in p.glob("*.json"):
            if j.name.endswith(".llm_calls.json"):
                continue
            try:
                d = json.loads(j.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(d, dict) or "metadata" not in d:
                continue
            if best is None or j.stat().st_mtime >= best[0]:
                best = (j.stat().st_mtime, p, j, d)
    return best


def count_list_field(obj, key: str) -> int:
    if not isinstance(obj, dict):
        return 0
    v = obj.get(key)
    return len(v) if isinstance(v, list) else 0


def analyze_one(idx: int) -> dict:
    race, strat, mmap = JOBS[idx]
    item = latest_valid(idx)
    out = {
        "idx": idx,
        "race": race,
        "strategy": strat,
        "map": mmap,
        "ok": False,
    }
    if item is None:
        out["error"] = "NO_VALID_JSON"
        return out
    _, p, jpath, d = item
    meta = d["metadata"]
    inter = d.get("interactions") or []
    dropped_u = dropped_m = exec_err = reasoning_ne = 0
    minerals = []
    for it in inter:
        if not isinstance(it, dict):
            continue
        dropped_u += count_list_field(it, "dropped_unknown_names")
        dropped_m += count_list_field(it, "dropped_unmapped_names")
        dec = it.get("decision") or {}
        if isinstance(dec, dict):
            dropped_u += count_list_field(dec, "dropped_unknown_names")
            dropped_m += count_list_field(dec, "dropped_unmapped_names")
            for act in dec.get("mapped_actions") or []:
                if isinstance(act, dict) and act.get("error"):
                    exec_err += 1
            if dec.get("provider_reasoning"):
                reasoning_ne += 1
        qt = it.get("queue_transition") or {}
        if isinstance(qt, dict):
            dropped_u += count_list_field(qt, "dropped_unknown_names")
            dropped_m += count_list_field(qt, "dropped_unmapped_names")
        if it.get("provider_reasoning"):
            reasoning_ne += 1
        obs = it.get("observation_structured") or {}
        if isinstance(obs, dict):
            mins = obs.get("minerals")
            if mins is None and isinstance(obs.get("resources"), dict):
                mins = obs["resources"].get("minerals")
            if isinstance(mins, (int, float)):
                minerals.append(mins)

    log_hits = {}
    abandoned = 0
    cant_place = 0
    for lp in p.glob("*.log"):
        text = lp.read_text(encoding="utf-8", errors="ignore")
        abandoned += len(re.findall(r"Abandoned stuck RUNNING", text))
        cant_place += len(re.findall(r"Can't find free position", text))
        for pat in PATTERNS:
            if re.search(pat, text, re.I):
                log_hits[pat] = log_hits.get(pat, 0) + len(
                    re.findall(pat, text, re.I)
                )

    # Sample strategy path from first interaction
    strategy_path = None
    if inter:
        strategy_path = inter[0].get("strategy")

    out.update(
        {
            "ok": True,
            "dir": p.name,
            "json": jpath.name,
            "result": meta.get("result"),
            "duration": meta.get("game_duration_formatted"),
            "duration_s": meta.get("game_duration_seconds"),
            "cycles": len(inter),
            "llm_count": meta.get("llm_interaction_count"),
            "dropped_unknown": dropped_u,
            "dropped_unmapped": dropped_m,
            "exec_err": exec_err,
            "reasoning_nonempty": reasoning_ne,
            "abandoned_stuck": abandoned,
            "cant_find_position": cant_place,
            "minerals_max": max(minerals) if minerals else None,
            "minerals_avg": round(sum(minerals) / len(minerals), 1)
            if minerals
            else None,
            "log_hits": log_hits,
            "macro": meta.get("macro_metrics") or {},
            "strategy_field": strategy_path,
            "top_agent": str(
                ROOT / "SKILL" / race / strat / "Top_agent.md"
            ),
        }
    )
    return out


def main() -> None:
    rows = [analyze_one(i) for i in range(7)]
    print("=== MATCH SUMMARY ===")
    for r in rows:
        if not r["ok"]:
            print(
                f"run{r['idx']} {r['race']}/{r['strategy']}@{r['map']}: "
                f"{r.get('error')}"
            )
            continue
        print(
            f"run{r['idx']} {r['race']}/{r['strategy']}@{r['map']} "
            f"=> {r['result']} {r['duration']}"
        )
        print(f"  dir={r['dir']}")
        print(
            f"  cycles={r['cycles']} llm={r['llm_count']} "
            f"unknown={r['dropped_unknown']} unmapped={r['dropped_unmapped']} "
            f"exec_err={r['exec_err']} reasoning_ne={r['reasoning_nonempty']} "
            f"abandoned={r['abandoned_stuck']} cant_place={r['cant_find_position']}"
        )
        print(
            f"  minerals max={r['minerals_max']} avg={r['minerals_avg']}"
        )
        print(f"  strategy_field={r['strategy_field']}")
        print(f"  top_agent={r['top_agent']}")
        if r["macro"]:
            interesting = {
                k: v
                for k, v in r["macro"].items()
                if any(
                    x in k.lower()
                    for x in (
                        "mineral",
                        "gas",
                        "supply",
                        "worker",
                        "army",
                        "base",
                        "unit",
                        "abandon",
                        "drop",
                        "error",
                    )
                )
            }
            if interesting:
                print(f"  macro={interesting}")
        if r["log_hits"]:
            print(f"  log_hits={r['log_hits']}")

    out_path = BATCH / "runner_logs" / "analysis_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
