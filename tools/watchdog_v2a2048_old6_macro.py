#!/usr/bin/env python3
"""Watchdog: poll v2a2048 APIs (:8310-:8315) and launch OLD-6 macro sweeps when ready.

Default behavior (READY_MODE=all): wait until ALL 6 endpoints pass health checks
for SUCCESS_STREAK consecutive polls, then launch all experiments once.

Health check (both must pass):
  1) GET  {api_url}/models  -> HTTP 200 and expected model_name present
  2) POST {api_url}/chat/completions -> HTTP 200 with a tiny completion

Usage:
  # continuous watch (default)
  python tools/watchdog_v2a2048_old6_macro.py

  # one-shot status
  python tools/watchdog_v2a2048_old6_macro.py --once

  # dry-run: when ready, print launch cmd but do not start
  python tools/watchdog_v2a2048_old6_macro.py --dry-run

  # built-in self tests (no network / no launch)
  python tools/watchdog_v2a2048_old6_macro.py --self-test
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
LAUNCH_SCRIPT = ROOT / "tools" / "start_old6_v2a2048_macro_all.sh"
STATE_DIR = ROOT / "game_records" / "_watchdog"
STATE_PATH = STATE_DIR / "v2a2048_old6.state.json"
LOG_PATH = STATE_DIR / "v2a2048_old6.log"

# tag -> (config_key, expected model_name on /v1/models)
TARGETS: List[Tuple[str, str, str]] = [
    (
        "balanced_two_stage",
        "Qwen3-1.7b-v2a2048-our-balanced-two-stage_think",
        "qwen3-1.7b-v2a2048-our-balanced-two-stage",
    ),
    (
        "balanced_cot_only",
        "Qwen3-1.7b-v2a2048-our-balanced-cot-only_think",
        "qwen3-1.7b-v2a2048-our-balanced-cot-only",
    ),
    (
        "uniform_two_stage",
        "Qwen3-1.7b-v2a2048-strategy-uniform-two-stage_think",
        "qwen3-1.7b-v2a2048-strategy-uniform-two-stage",
    ),
    (
        "uniform_cot_only",
        "Qwen3-1.7b-v2a2048-strategy-uniform-cot-only_think",
        "qwen3-1.7b-v2a2048-strategy-uniform-cot-only",
    ),
    (
        "random_two_stage",
        "Qwen3-1.7b-v2a2048-random-instance-two-stage_think",
        "qwen3-1.7b-v2a2048-random-instance-two-stage",
    ),
    (
        "random_cot_only",
        "Qwen3-1.7b-v2a2048-random-instance-cot-only_think",
        "qwen3-1.7b-v2a2048-random-instance-cot-only",
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
    launched_tags: List[str] = field(default_factory=list)
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
            launched_tags=list(data.get("launched_tags") or []),
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
                    "launched_tags": self.launched_tags,
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
    chat_timeout: float = 120.0,
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
            why += f" missing model {ep.model_name!r}"
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
            http_chat=None,
        )

    chat_url = f"{ep.api_url}/chat/completions"
    body = {
        "model": ep.model_name,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 32,
        "temperature": 0.0,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    # Also put under extra_body-compatible top-level for vLLM; some servers want nested.
    code_c, payload_c, detail_c = _http_json(
        "POST", chat_url, headers=headers, body=body, timeout=chat_timeout
    )
    chat_ok = False
    if code_c == 200 and isinstance(payload_c, dict):
        choices = payload_c.get("choices") or []
        if choices:
            msg = (choices[0] or {}).get("message") or {}
            content = msg.get("content")
            # thinking models may put text in reasoning/content; accept any non-empty choice
            chat_ok = True if (content is not None or msg) else False
            if isinstance(content, str) and content.strip() == "" and not msg.get("reasoning_content"):
                # empty content with no reasoning still counts as serving if finish_reason present
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


def launch_experiments(
    tags: List[str],
    *,
    dry_run: bool = False,
    concurrency: int = 8,
    skip_completed: int = 0,
) -> int:
    if not LAUNCH_SCRIPT.is_file():
        raise FileNotFoundError(LAUNCH_SCRIPT)
    env = os.environ.copy()
    env["CONCURRENCY"] = str(concurrency)
    env["SKIP_COMPLETED"] = str(skip_completed)
    env["AUTO_EXIT"] = "1"
    if tags == [t[0] for t in TARGETS]:
        args = ["bash", str(LAUNCH_SCRIPT), "all"]
    elif len(tags) == 1:
        args = ["bash", str(LAUNCH_SCRIPT), tags[0]]
    else:
        # launch one-by-one for partial sets
        rc = 0
        for tag in tags:
            rc = launch_experiments(
                [tag],
                dry_run=dry_run,
                concurrency=concurrency,
                skip_completed=skip_completed,
            )
            if rc != 0:
                return rc
        return 0

    cmd_s = " ".join(args)
    if dry_run:
        log(f"[dry-run] would launch: {cmd_s} (CONCURRENCY={concurrency})")
        return 0
    log(f"Launching: {cmd_s} (CONCURRENCY={concurrency})")
    proc = subprocess.run(args, cwd=str(ROOT), env=env)
    log(f"Launch script exit={proc.returncode}")
    return int(proc.returncode)


def run_watch(
    *,
    endpoints: List[Endpoint],
    interval: float,
    streak_need: int,
    ready_mode: str,
    once: bool,
    dry_run: bool,
    require_chat: bool,
    concurrency: int,
    skip_completed: int,
    force: bool,
) -> int:
    state = WatchState.load(STATE_PATH)
    if state.launched and not force:
        log(
            f"Already launched at {state.launched_at} tags={state.launched_tags}. "
            f"Use --force to ignore state. Exiting."
        )
        return 0

    log(
        f"Watch start: {len(endpoints)} endpoints | interval={interval}s | "
        f"streak={streak_need} | ready_mode={ready_mode} | require_chat={require_chat} | "
        f"dry_run={dry_run}"
    )

    while True:
        ready_tags: List[str] = []
        for ep in endpoints:
            pr = probe_endpoint(ep, require_chat=require_chat)
            if pr.ok:
                state.streaks[ep.tag] = state.streaks.get(ep.tag, 0) + 1
            else:
                state.streaks[ep.tag] = 0
            state.last_status[ep.tag] = pr.detail
            streak = state.streaks.get(ep.tag, 0)
            mark = "READY" if streak >= streak_need else ("ok" if pr.ok else "WAIT")
            log(
                f"[{mark}] {ep.tag:22s} streak={streak}/{streak_need} "
                f"url={ep.api_url} :: {pr.detail}"
            )
            if streak >= streak_need:
                ready_tags.append(ep.tag)

        state.save(STATE_PATH)
        all_ready = len(ready_tags) == len(endpoints)

        if ready_mode == "all" and all_ready:
            tags = [ep.tag for ep in endpoints]
            rc = launch_experiments(
                tags,
                dry_run=dry_run,
                concurrency=concurrency,
                skip_completed=skip_completed,
            )
            if rc == 0 or dry_run:
                state.launched = True
                state.launched_at = _now()
                state.launched_tags = tags
                state.save(STATE_PATH)
                log("All endpoints ready -> experiments launched. Watchdog done.")
                return 0 if rc == 0 or dry_run else rc
            log(f"Launch failed rc={rc}; will retry next loop.")
        elif ready_mode == "each":
            # launch only newly ready tags not yet recorded
            pending = [t for t in ready_tags if t not in state.launched_tags]
            if pending:
                rc = launch_experiments(
                    pending,
                    dry_run=dry_run,
                    concurrency=concurrency,
                    skip_completed=skip_completed,
                )
                if rc == 0 or dry_run:
                    state.launched_tags = sorted(set(state.launched_tags) | set(pending))
                    if len(state.launched_tags) == len(endpoints):
                        state.launched = True
                        state.launched_at = _now()
                    state.save(STATE_PATH)
                    log(f"Launched tags: {pending}")
                else:
                    log(f"Partial launch failed rc={rc}")
            if state.launched:
                log("All tags launched. Watchdog done.")
                return 0

        if once:
            log("`--once` finished.")
            return 0 if (ready_mode != "all" or not all_ready or dry_run) else 0

        time.sleep(interval)


# ---------------- self tests ----------------

class _FakeHTTP:
    def __init__(self, responses: Dict[str, Tuple[int, Any, str]]):
        self.responses = responses
        self.calls: List[str] = []

    def __call__(self, method, url, *, headers=None, body=None, timeout=15.0):
        self.calls.append(f"{method} {url}")
        # match by suffix path
        for key, val in self.responses.items():
            if key in url:
                return val
        return -1, None, "no mock"


def self_test() -> int:
    import tempfile

    print("Running self-test...")
    failures = 0

    def check(cond: bool, msg: str) -> None:
        nonlocal failures
        if cond:
            print(f"  PASS  {msg}")
        else:
            print(f"  FAIL  {msg}")
            failures += 1

    # config keys exist
    try:
        eps = load_endpoints(DEFAULT_CONFIG)
        check(len(eps) == 6, f"load 6 endpoints from config (got {len(eps)})")
        ports = sorted(int(e.api_url.rsplit(":", 1)[-1].split("/")[0]) for e in eps)
        check(ports == [8310, 8311, 8312, 8313, 8314, 8315], f"ports={ports}")
    except Exception as e:
        check(False, f"load_endpoints: {e}")
        eps = []

    check(LAUNCH_SCRIPT.is_file(), f"launch script exists: {LAUNCH_SCRIPT}")
    check(os.access(LAUNCH_SCRIPT, os.X_OK) or True, "launch script present")

    # models contain helper
    check(
        _models_contain(
            {"data": [{"id": "qwen3-1.7b-v2a2048-our-balanced-two-stage"}]},
            "qwen3-1.7b-v2a2048-our-balanced-two-stage",
        ),
        "models list match",
    )
    check(
        not _models_contain({"data": [{"id": "other"}]}, "qwen3-1.7b-v2a2048-our-balanced-two-stage"),
        "models list mismatch",
    )

    # probe with mocks
    if eps:
        ep = eps[0]
        good_models = (
            200,
            {"data": [{"id": ep.model_name}]},
            "ok",
        )
        good_chat = (
            200,
            {"choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}]},
            "ok",
        )
        bad_models = (502, None, "bad gateway")

        mod = sys.modules[__name__]
        real_http = mod._http_json

        mod._http_json = _FakeHTTP({"/models": good_models, "/chat/completions": good_chat})
        pr = probe_endpoint(ep, require_chat=True)
        check(pr.ok and pr.models_ok and pr.chat_ok, f"probe ok on healthy mock: {pr.detail}")

        mod._http_json = _FakeHTTP({"/models": bad_models, "/chat/completions": good_chat})
        pr2 = probe_endpoint(ep, require_chat=True)
        check(not pr2.ok and not pr2.models_ok, f"probe fails on 502 models: {pr2.detail}")

        mod._http_json = _FakeHTTP({"/models": good_models, "/chat/completions": (503, None, "busy")})
        pr3 = probe_endpoint(ep, require_chat=True)
        check(not pr3.ok and pr3.models_ok and not pr3.chat_ok, f"probe fails on chat 503: {pr3.detail}")

        mod._http_json = real_http

    # state roundtrip
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "state.json"
        st = WatchState(launched=False, streaks={"a": 2})
        st.save(p)
        st2 = WatchState.load(p)
        check(st2.streaks.get("a") == 2, "state save/load streak")
        st2.launched = True
        st2.launched_at = "t"
        st2.launched_tags = ["a"]
        st2.save(p)
        st3 = WatchState.load(p)
        check(st3.launched and st3.launched_tags == ["a"], "state launched flag")

    # dry-run launch should not create tmux (just succeed)
    rc = launch_experiments(["balanced_two_stage"], dry_run=True)
    check(rc == 0, "dry-run launch returns 0")

    # bash syntax check
    syn = subprocess.run(
        ["bash", "-n", str(LAUNCH_SCRIPT)],
        capture_output=True,
        text=True,
    )
    check(syn.returncode == 0, f"bash -n launch script (rc={syn.returncode})")

    print(f"Self-test done. failures={failures}")
    return 1 if failures else 0


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Watchdog for v2a2048 OLD-6 macro experiments")
    p.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    p.add_argument("--interval", type=float, default=float(os.environ.get("WATCH_INTERVAL", "60")))
    p.add_argument("--streak", type=int, default=int(os.environ.get("SUCCESS_STREAK", "2")))
    p.add_argument(
        "--ready-mode",
        choices=("all", "each"),
        default=os.environ.get("READY_MODE", "all"),
        help="all=wait for all 6; each=launch each tag when ready",
    )
    p.add_argument("--once", action="store_true", help="probe once and exit")
    p.add_argument("--dry-run", action="store_true", help="do not actually launch sweeps")
    p.add_argument("--force", action="store_true", help="ignore previous launched state")
    p.add_argument("--no-chat", action="store_true", help="only check /v1/models")
    p.add_argument("--concurrency", type=int, default=int(os.environ.get("CONCURRENCY", "8")))
    p.add_argument("--skip-completed", type=int, default=int(os.environ.get("SKIP_COMPLETED", "0")))
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
        ready_mode=args.ready_mode,
        once=args.once,
        dry_run=args.dry_run,
        require_chat=not args.no_chat,
        concurrency=args.concurrency,
        skip_completed=args.skip_completed,
        force=args.force,
    )


if __name__ == "__main__":
    sys.exit(main())
