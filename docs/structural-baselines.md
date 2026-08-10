# Structural harness baselines

This repository provides five knowledge-free structural baselines that share
the same frozen SC2 decision context, canonical action space, mapper, and
`ExecutionScheduler`.

| Mode | Harness | Calls per normal decision | Trace directory |
|---|---|---:|---|
| `plan-execute` | one Planner, then 1–4 sequential Executors | 2–5 | `pe_traces/` |
| `self-refine` | Init, Feedback, and up to two Refine rounds | 2–5 | `sr_traces/` |
| `suntzu` | Planner, plan verification/refinement, Executor verification/retry | variable | `suntzu_traces/` |
| `hima` | three independent Advisors, then one Leader | 4 | `hima_traces/` |
| `cos` | current-frame L1 summary, then L2 over the latest five summaries | 2 | `cos_traces/` |

All five modes:

- use `decision_model_key` for every role through
  `API_Tools.llm_caller.call_openai_detailed`;
- capture one observation per macro decision;
- do not use `DataSubAgent`, retrieval, knowledge datasets, or persistent
  cross-game memory;
- return the common `{reason, ordered_names}` contract;
- record every subcall in `*.llm_calls.json`;
- use interaction schema version 5;
- leave malformed decisions fail-closed so the old uncommitted queue remains.

## Run

```bash
python tools/run_experiment.py \
  --decision-agent-mode plan-execute \
  --decision-model qwen3-32b \
  --strategy marine_rush \
  --bot-race terran \
  --enemy-race zerg
```

Replace `plan-execute` with `self-refine`, `suntzu`, `hima`, or `cos`.

Probe the two generic structural baselines without SC2:

```bash
python tools/probe_structural_baselines.py \
  --decision-agent-mode plan-execute \
  --model-key qwen3-32b
```

Probe the SC2-derived structural baselines:

```bash
python tools/probe_sc2_structural_baselines.py \
  --decision-agent-mode suntzu \
  --model-key qwen3-32b
```

For CoS, the probe executes at least six consecutive cycles per race to verify
history growth and truncation.

Run the 10-match diverse smoke matrix with up to 10 concurrent SC2 clients:

```bash
python tools/run_structural_baseline_smoke10.py \
  --modes plan-execute,self-refine,suntzu,hima,cos \
  --decision-model qwen3-32b \
  --concurrency 10
```

## Verification record — 2026-08-10

Static verification after audit and fixes:

```text
python -m compileall ...                         PASS
python -m pytest tools/tests ...                 182 passed
git diff --check                                PASS
forbidden knowledge/local-model dependency grep 0 matches
```

Real SC2 smoke configuration:

```text
model profile: qwen3-32b (non-thinking)
map: KairosJunctionLE
enemy build: macro
game-time limit: 360 seconds
decision interval: 60 game seconds
10 matches per mode, 50 total
difficulties: easy, medium, mediumhard, hard, harder
```

| Mode | Matches | Victory | Tie | Defeat | Decisions | Invalid decisions | Provider errors | Mean calls/decision |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `plan-execute` | 10 | 0 | 10 | 0 | 73 | 0 | 0 | 4.64 |
| `self-refine` | 10 | 1 | 9 | 0 | 95 | 0 | 0 | 3.87 |
| `suntzu` | 10 | 1 | 9 | 0 | 84 | 0 | 0 | 5.43 |
| `hima` | 10 | 0 | 10 | 0 | 93 | 0 | 0 | 4.00 |
| `cos` | 10 | 1 | 9 | 0 | 74 | 1 | 0 | 1.99 |

All 50 match processes exited with code 0 and produced parseable match
results. The single CoS invalid decision was a malformed L1 response at cycle
2; the runtime retained the old queue as designed and the match completed as a
tie. The 360-second ties are smoke-test timeouts, not natural outcome
comparisons.

## Audit record

The post-implementation audit found and fixed one failure-semantics defect:
SunTzu previously stopped immediately when the first Executor response was
malformed JSON. It now feeds `missing_or_malformed_decision` into the bounded
Executor retry loop, matching the implementation plan. A regression test
covers the recovered call order.

Method-specific research notes are under:

- [`structural_baselines/`](structural_baselines/)
- [`sc2_structural_baselines/`](sc2_structural_baselines/)

The completed implementation plans are archived under
[`archive/2026-08-10-structural-baselines/`](archive/2026-08-10-structural-baselines/).
