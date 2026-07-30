"""Dig dropped names / abandoned actions / unit counts from kn30 records."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

BATCH = Path(__file__).resolve().parents[1] / "game_records" / "kn30"

TARGETS = {
    1: "20260730_130115_t_bio_au_run1",
    2: "20260730_130701_t_2bmt_ab_run2",
    0: "20260730_125622_t_mrush_kj_run0",
    3: "20260730_130559_p_4gate_au_run3",
}


def load(name: str):
    p = BATCH / name / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8"))


def walk_drop(obj, acc: Counter):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("dropped_unknown_names", "dropped_unmapped_names") and isinstance(
                v, list
            ):
                for item in v:
                    if isinstance(item, str):
                        acc[f"{k}:{item}"] += 1
                    else:
                        acc[f"{k}:{item}"] += 1
            else:
                walk_drop(v, acc)
    elif isinstance(obj, list):
        for x in obj:
            walk_drop(x, acc)


def last_units(d):
    inter = d.get("interactions") or []
    if not inter:
        return {}
    obs = inter[-1].get("observation_structured") or {}
    # try common shapes
    for key in ("units", "my_units", "unit_counts", "friendly_units"):
        if key in obs and isinstance(obs[key], dict):
            return obs[key]
    # flatten numbers from observation text? skip
    text = inter[-1].get("observation_at_this_moment") or ""
    counts = dict(re.findall(r"([A-Za-z][A-Za-z0-9]+)\s*[:=]\s*(\d+)", text))
    return {k: int(v) for k, v in counts.items() if int(v) > 0}


def abandoned_from_log(name: str) -> Counter:
    c = Counter()
    log = BATCH / name / f"{name}.log"
    if not log.exists():
        return c
    text = log.read_text(encoding="utf-8", errors="ignore")
    for m in re.finditer(
        r"Abandoned stuck RUNNING action ([A-Z0-9_]+) after", text
    ):
        c[m.group(1)] += 1
    for m in re.finditer(
        r"Can't find free position to build ([A-Z0-9_]+) in!", text
    ):
        c[f"NO_POS:{m.group(1)}"] += 1
    return c


def main():
    for idx, name in TARGETS.items():
        print("=" * 60, name)
        d = load(name)
        drops = Counter()
        walk_drop(d, drops)
        print("drops:", dict(drops))
        print("result/duration:", d["metadata"].get("result"), d["metadata"].get("game_duration_formatted"))
        units = last_units(d)
        # print top units
        if units:
            items = sorted(units.items(), key=lambda kv: (-kv[1], kv[0]))[:25]
            print("last_units_sample:", items)
        abd = abandoned_from_log(name)
        print("abandoned/no_pos top:", abd.most_common(20))
        # scan reasons mentioning techlab/addon
        reasons = []
        for it in d.get("interactions") or []:
            dec = it.get("decision") or {}
            reason = dec.get("reason") or it.get("decision_reason") or ""
            q = it.get("new_queue") or dec.get("ordered_names") or []
            if any(
                x in str(q) + reason
                for x in ("TechLab", "Reactor", "Factory", "Starport", "Barracks")
            ):
                reasons.append(
                    {
                        "t": it.get("game_time"),
                        "q": q[:12] if isinstance(q, list) else q,
                        "reason": (reason or "")[:220],
                    }
                )
        print("sample queues with production/addons:")
        for r in reasons[:6]:
            print(" ", r)


if __name__ == "__main__":
    main()
