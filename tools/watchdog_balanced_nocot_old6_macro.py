#!/usr/bin/env python3
"""Watchdog: wait until both balanced-nocot vLLM endpoints are healthy, then launch OLD-6.

Targets (thinking OFF / is_reasoning=false):
  stage1     @ http://172.18.30.122:8010/v1
             model qwen3-1.7b-our-balanced-nocot-stage1
  mix_grpo   @ http://172.18.30.122:8011/v1
             model qwen3-1.7b-our-balanced-nocot-mix-grpo-v2-nothink

When READY (SUCCESS_STREAK consecutive healthy polls for BOTH):
  bash tools/start_old6_balanced_nocot_pair_macro.sh all
    - each group concurrency=20, no veryhard, 270 jobs

Usage:
  python tools/watchdog_balanced_nocot_old6_macro.py
  python tools/watchdog_balanced_nocot_old6_macro.py --once --dry-run
  python tools/watchdog_balanced_nocot_old6_macro.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "API_config" / "config.json"
LAUNCH_SCRIPT = ROOT / "tools" / "start_old6_balanced_nocot_pair_macro.sh"
STATE_DIR = ROOT / "game_records" / "_watchdog"
STATE_PATH = STATE_DIR / "balanced_nocot_old6.state.json"
LOG_PATH = STATE_DIR / "balanced_nocot_old6.log"

# tag -> config_key -> expected served model id
TARGETS: List[Tuple[str, str, str]] = [
    (
        "stage1",
        "Qwen3-1.7b-our-balanced-nocot-stage1",
        "qwen3-1.7b-our-balanced-nocot-stage1",
    ),
    (
        "mix_grpo_v2",
        "Qwen3-1.7b-our-balanced-nocot-mix-grpo-v2-nothink",
        "qwen3-1.7b-our-balanced-nocot-mix-grpo-v2-nothink",
    ),
]


@dataclass
class Endpoint:
    tag: str
    config_key: str
    model_name: str
    api_url: str
    api_key: str


@dataclass
class ProbeResult:
    ok: bool
    models_ok: bool
    chat_ok: bool
    detail: str
    http_models: Optional[int] = None
    http_chat: Optional[int] = None


@dataclass
class WatchState:
    launched: bool = False
    launched_at: Optional[str] = None
    streaks: Dict[str, int] = field(default_factory=dict)
    last_status: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "WatchState":
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text())
        except Exception:
            return cls()
        return cls(
            launched=bool(data.get("launched")),
            launched_at=data.get("launched_at"),
            streaks={k: int(v) for k, v in (data.get("streaks") or {}).items()},
            last_status={k: str(v) for k, v in (data.get("last_status") or {}).items()},
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "launched": self.launched,
                    "launched_at": self.launched_at,
                    "streaks": self.streaks,
                    "last_status": self.last_status,
                    "updated_at": _now(),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    line = f"[{_now()}] {msg}"
    print(line, flush=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_endpoints(config_path: Path) -> List[Endpoint]:
    cfg = json.loads(config_path.read_text())
    pool = cfg.get("llm_agents_pool") or {}
    out: List[Endpoint] = []
    for tag, key, model_name in TARGETS:
        entry = pool.get(key)
        if not entry:
            raise KeyError(f"missing config key: {key}")
        api_url = (entry.get("api_url") or "").rstrip("/")
        api_key = entry.get("api_key") or ""
        cfg_model = entry.get("model_name") or ""
        if cfg_model != model_name:
            raise ValueError(f"{key}: model_name mismatch {cfg_model!r} vs {model_name!r}")
        if entry.get("is_reasoning") is True:
            raise ValueError(f"{key}: expected is_reasoning=false (nothink experiment)")
        if not api_url or not api_key:
            raise ValueError(f"{key}: api_url/api_key missing")
        out.append(
            Endpoint(
                tag=tag,
                config_key=key,
                model_name=model_name,
                api_url=api_url,
                api_key=api_key,
            )
        )
    return out


def _http_json(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Dict[str, Any]] = None,
    timeout: float = 15.0,
) -> Tuple[int, Any, str]:
    data = None
    req_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            code = int(resp.status)
            try:
                return code, json.loads(raw) if raw else None, raw[:300]
            except Exception:
                return code, None, raw[:300]
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return int(e.code), None, raw[:300] or str(e)
    except Exception as e:
        return -1, None, str(e)


def _models_contain(payload: Any, model_name: str) -> bool:
    if not isinstance(payload, dict):
        return False
    data = payload.get("data")
    if not isinstance(data, list):
        return False
    for item in data:
        if not isinstance(item, dict):
            continue
        mid = item.get("id") or item.get("model") or item.get("root")
        if mid == model_name:
            return True
    return False


def probe_endpoint(
    ep: Endpoint,
    *,
    models_timeout: float = 10.0,
    chat_timeout: float = 180.0,
    require_chat: bool = True,
) -> ProbeResult:
    headers = {"Authorization": f"Bearer {ep.api_key}"}
    models_url = f"{ep.api_url}/models"
    code_m, payload_m, detail_m = _http_json(
        "GET", models_url, headers=headers, timeout=models_timeout
    )
    models_ok = code_m == 200 and _models_contain(payload_m, ep.model_name)
    if not models_ok:
        why = f"models http={code_m}"
        if code_m == 200:
            served = []
            if isinstance(payload_m, dict):
                for item in payload_m.get("data") or []:
                    if isinstance(item, dict):
                        served.append(item.get("id") or "?")
            why += f" missing {ep.model_name!r} (served={served})"
        else:
            why += f" {detail_m}"
        return ProbeResult(
            ok=False,
            models_ok=False,
            chat_ok=False,
            detail=why,
            http_models=code_m,
        )

    if not require_chat:
        return ProbeResult(
            ok=True,
            models_ok=True,
            chat_ok=True,
            detail="models ok (chat skipped)",
            http_models=code_m,
        )

    chat_url = f"{ep.api_url}/chat/completions"
    body: Dict[str, Any] = {
        "model": ep.model_name,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 32,
        "temperature": 0.0,
        # Explicitly disable thinking for health probe as well.
        "chat_template_kwargs": {"enable_thinking": False},
    }
    code_c, payload_c, detail_c = _http_json(
        "POST", chat_url, headers=headers, body=body, timeout=chat_timeout
    )
    chat_ok = False
    if code_c == 200 and isinstance(payload_c, dict):
        choices = payload_c.get("choices") or []
        if choices:
            msg = (choices[0] or {}).get("message") or {}
            content = msg.get("content")
            chat_ok = True if (content is not None or msg) else False
            if isinstance(content, str) and content.strip() == "" and not msg.get(
                "reasoning_content"
            ):
                chat_ok = bool((choices[0] or {}).get("finish_reason"))
    if not chat_ok:
        return ProbeResult(
            ok=False,
            models_ok=True,
            chat_ok=False,
            detail=f"models ok; chat http={code_c} {detail_c}",
            http_models=code_m,
            http_chat=code_c,
        )
    return ProbeResult(
        ok=True,
        models_ok=True,
        chat_ok=True,
        detail="models+chat ok",
        http_models=code_m,
        http_chat=code_c,
    )


def launch_experiments(*, dry_run: bool = False, skip_completed: int = 0) -> int:
    if not LAUNCH_SCRIPT.is_file():
        raise FileNotFoundError(LAUNCH_SCRIPT)
    env = os.environ.copy()
    env["SKIP_COMPLETED"] = str(skip_completed)
    env["AUTO_EXIT"] = "1"
    env["CONCURRENCY"] = env.get("CONCURRENCY", "20")
    args = ["bash", str(LAUNCH_SCRIPT), "all"]
    cmd_s = " ".join(args)
    if dry_run:
        log(f"[dry-run] would launch: {cmd_s} (CONCURRENCY={env['CONCURRENCY']})")
        return 0
    log(f"Launching: {cmd_s} (CONCURRENCY={env['CONCURRENCY']})")
    proc = subprocess.run(args, cwd=str(ROOT), env=env)
    log(f"Launch script exit={proc.returncode}")
    return int(proc.returncode)


def run_watch(
    *,
    endpoints: List[Endpoint],
    interval: float,
    streak_need: int,
    once: bool,
    dry_run: bool,
    require_chat: bool,
    skip_completed: int,
    force: bool,
) -> int:
    state = WatchState.load(STATE_PATH)
    if state.launched and not force:
        log(
            f"Already launched at {state.launched_at}. "
            f"Use --force to ignore state. Exiting."
        )
        return 0

    log(
        f"Watch start: {[e.tag for e in endpoints]} | interval={interval}s | "
        f"streak={streak_need} | require_chat={require_chat} | dry_run={dry_run}"
    )
    for ep in endpoints:
        log(f"  expect {ep.tag}: {ep.model_name} @ {ep.api_url}")

    while True:
        all_ready = True
        for ep in endpoints:
            pr = probe_endpoint(ep, require_chat=require_chat)
            if pr.ok:
                state.streaks[ep.tag] = state.streaks.get(ep.tag, 0) + 1
            else:
                state.streaks[ep.tag] = 0
                all_ready = False
            state.last_status[ep.tag] = pr.detail
            streak = state.streaks.get(ep.tag, 0)
            if streak < streak_need:
                all_ready = False
            mark = "READY" if streak >= streak_need else ("ok" if pr.ok else "WAIT")
            log(
                f"[{mark}] {ep.tag:12s} streak={streak}/{streak_need} "
                f"url={ep.api_url} :: {pr.detail}"
            )

        state.save(STATE_PATH)

        if all_ready and all(
            state.streaks.get(ep.tag, 0) >= streak_need for ep in endpoints
        ):
            rc = launch_experiments(dry_run=dry_run, skip_completed=skip_completed)
            if rc == 0 or dry_run:
                state.launched = True
                state.launched_at = _now()
                state.save(STATE_PATH)
                log("API ready -> experiments launched. Watchdog done.")
                return 0 if rc == 0 or dry_run else rc
            log(f"Launch failed rc={rc}; will retry next loop.")

        if once:
            log("`--once` finished.")
            return 0

        time.sleep(interval)


def self_test() -> int:
    failures = 0

    def check(cond: bool, msg: str) -> None:
        nonlocal failures
        if cond:
            print(f"  PASS  {msg}")
        else:
            print(f"  FAIL  {msg}")
            failures += 1

    print("Running self-test...")
    try:
        eps = load_endpoints(DEFAULT_CONFIG)
        check(len(eps) == 2, f"load 2 endpoints (got {len(eps)})")
        s1 = next(e for e in eps if e.tag == "stage1")
        check(
            s1.api_url == "http://172.18.30.122:8010/v1",
            f"stage1 url={s1.api_url}",
        )
        check(
            s1.model_name == "qwen3-1.7b-our-balanced-nocot-stage1",
            f"stage1 model={s1.model_name}",
        )
        mg = next(e for e in eps if e.tag == "mix_grpo_v2")
        check(
            mg.api_url == "http://172.18.30.122:8011/v1",
            f"mix url={mg.api_url}",
        )
        check(
            mg.model_name == "qwen3-1.7b-our-balanced-nocot-mix-grpo-v2-nothink",
            f"mix model={mg.model_name}",
        )
    except Exception as e:
        check(False, f"load_endpoints: {e}")
        eps = []

    check(LAUNCH_SCRIPT.is_file(), f"launch script exists: {LAUNCH_SCRIPT}")
    syn = subprocess.run(
        ["bash", "-n", str(LAUNCH_SCRIPT)], capture_output=True, text=True
    )
    check(syn.returncode == 0, f"bash -n launch script (rc={syn.returncode})")

    # Confirm config entries force thinking off.
    cfg = json.loads(DEFAULT_CONFIG.read_text())
    pool = cfg.get("llm_agents_pool") or {}
    for tag, key, _model in TARGETS:
        entry = pool.get(key) or {}
        check(entry.get("is_reasoning") is False, f"{tag} is_reasoning=false")
        nr = entry.get("non_reasoning_extra_body") or {}
        ctk = nr.get("chat_template_kwargs") or {}
        check(ctk.get("enable_thinking") is False, f"{tag} enable_thinking=false")

    if eps:
        ep = eps[0]
        mod = sys.modules[__name__]
        real = mod._http_json

        class Fake:
            def __init__(self, mapping):
                self.mapping = mapping

            def __call__(self, method, url, *, headers=None, body=None, timeout=15.0):
                for k, v in self.mapping.items():
                    if k in url:
                        return v
                return -1, None, "no mock"

        good_m = (200, {"data": [{"id": ep.model_name}]}, "ok")
        good_c = (
            200,
            {"choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}]},
            "ok",
        )
        wrong_m = (200, {"data": [{"id": "qwen3-0.6b"}]}, "ok")

        mod._http_json = Fake({"/models": good_m, "/chat/completions": good_c})
        pr = probe_endpoint(ep)
        check(pr.ok, f"healthy probe: {pr.detail}")

        mod._http_json = Fake({"/models": wrong_m, "/chat/completions": good_c})
        pr2 = probe_endpoint(ep)
        check(not pr2.ok and "missing" in pr2.detail, f"reject wrong model: {pr2.detail}")

        mod._http_json = real

    rc = launch_experiments(dry_run=True)
    check(rc == 0, "dry-run launch returns 0")

    print(f"Self-test done. failures={failures}")
    return 1 if failures else 0


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Watchdog for balanced-nocot OLD-6 macro experiments"
    )
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--interval", type=float, default=float(os.environ.get("WATCH_INTERVAL", "30")))
    p.add_argument("--streak", type=int, default=int(os.environ.get("SUCCESS_STREAK", "2")))
    p.add_argument("--once", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--no-chat", action="store_true")
    p.add_argument(
        "--skip-completed",
        type=int,
        default=int(os.environ.get("SKIP_COMPLETED", "0")),
    )
    p.add_argument("--self-test", action="store_true")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.self_test:
        return self_test()
    endpoints = load_endpoints(args.config)
    return run_watch(
        endpoints=endpoints,
        interval=args.interval,
        streak_need=max(1, args.streak),
        once=args.once,
        dry_run=args.dry_run,
        require_chat=not args.no_chat,
        skip_completed=args.skip_completed,
        force=args.force,
    )


if __name__ == "__main__":
    raise SystemExit(main())
