# SC2-Agent Knowledge

This branch runs a summary-guided macro decision agent for Terran, Protoss,
and Zerg. Supported launchers now default to the knowledge-backed `data-v2.2`
mode; the original single-call agent remains intact as the selectable `naive`
mode.

```text
strategy summary + observation + previous uncommitted canonical names
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
              naive                    data-v2.2
          one model call          MainAgent ↔ DataSubAgent
                                         ↕
                               local V2.2 SC2 dataset
                 │                           │
                 └─────────────┬─────────────┘
                               ▼
                    {reason, ordered_names}
                               ▼
                  canonical name → SC2 action
                               ▼
              deterministic ExecutionScheduler
```

The LLM does not choose a worker or production structure. It produces one
complete replacement queue of canonical names. The runtime owns prerequisite
checks, resource reservation, skip/overtake behavior, producer selection, and
command submission.

## Decision modes

- `data-v2.2` uses separately maintained prompts and a vendored copy of the
  V2.2 MainAgent, DataSubAgent, query tools, and complete dataset. MainAgent
  receives the original decision context plus data-shape and subagent-use
  guidance, and decides per decision whether a DataSubAgent query is useful.
- `data-v2.2-v2` preserves `data-v2.2` as V1 and adds an independent planning
  mode with deterministic task decomposition, preflight knowledge routing,
  horizon resource and production-throughput targets, crisis worker limits,
  executable queue assembly, match-local knowledge caching, and weapon-layer-
  gated air/ground responses. The 2026-08-04 same-six-match DeepSeek regression
  improved from 2W/4L to 2W/0L/4T with 156/156 successful V2 traces.
- `naive` uses the preserved `SC2_Agent/decision_agent.py` implementation. It
  shares neither prompt files nor orchestration code with either knowledge mode.

All three modes accept the same trigger context and return the same public contract:

```json
{
  "reason": "Public, concise explanation; not chain-of-thought.",
  "ordered_names": ["SupplyDepot", "Barracks", "Marine"]
}
```

The race-specific canonical allowlist is still the executable boundary. The
knowledge dataset may explain additional entities, but those cannot be emitted
as scheduler actions.

## Repository boundary

Only the `UniversalLLMBot` macro-planning path selects between the three modes.
The repository retains Sharpy, bundled `python-sc2`, example bots, ladder
launchers, mapping code, and deterministic execution. The V2.2 dependency
closures are copied under `SC2_Agent/knowledge_v2_2/` and
`SC2_Agent/knowledge_v2_2_v2/`; neither imports from or modifies the sibling
`SC2_DATA_Agent` repository.

`UniversalLLMBot`, `GameStarter`, and the supported CLIs all use `data-v2.2` by
default. Existing callers can select the preserved implementation explicitly
with `decision_agent_mode="naive"` or `--decision-agent-mode naive`.

## Decision semantics

A decision is requested once at the beginning, every 60 in-game seconds by
default, or when a non-empty queue becomes fully drained after a short
anti-loop guard. If one task remains, the queue is not drained. An accepted
empty queue is valid and waits for the normal interval.

Only canonical names not yet submitted to SC2 appear in the next decision
context. A new `ordered_names` list replaces all such local work, so important
unfinished items must be repeated. Already submitted commands are never
cancelled. The queue is a compact near-term horizon, normally no more than 20
names. Supply providers and workers are model-owned decisions and are not
inserted automatically.

Every strategy lives at `SKILL/<our_race>/<strategy>/Top_agent.md` and contains
one opponent-agnostic `# Summary`. Its `strategy_tools.py` automation profile
drives both real tactical behavior and the matching model-facing description.

| Race | Enabled strategies |
|---|---|
| Terran | `marine_rush`, `bio`, `blueflame_locks`, `two_base_matrix_tanks`, `yamato_rust_fleet` |
| Protoss | `four_gate`, `dark_templar_rush`, `robo`, `voidray`, `macro_stalkers` |
| Zerg | `twelve_pool`, `macro_roach`, `roach_hydra`, `lurkers`, `mutalisk` |

## Run

Configure model keys in the ignored `API_config/config.json`, then run the
default knowledge-backed mode. MainAgent and DataSubAgent each have an
independent model key and therefore may use different API endpoints or
credentials; both default to `Kimi-k2.5` non-thinking:

```powershell
python run_vs_ai.py `
  --decision-agent-mode data-v2.2 `
  --decision-model Kimi-k2.5 `
  --data-subagent-model Kimi-k2.5 `
  --decision-interval 60 `
  --force-strategy marine_rush `
  --enemy-race terran `
  --enemy-difficulty medium
```

Use the preserved implementation explicitly when a baseline is needed:

```powershell
python run_vs_ai.py `
  --decision-agent-mode naive `
  --decision-model Kimi-k2.5 `
  --force-strategy marine_rush
```

Select the planning-constrained V2 mode explicitly:

```powershell
python run_vs_ai.py `
  --decision-agent-mode data-v2.2-v2 `
  --decision-model DeepSeek-V4-flash `
  --data-subagent-model DeepSeek-V4-flash `
  --force-strategy lurkers
```

For one reproducible experiment:

```powershell
python tools\run_experiment.py `
  --decision-agent-mode data-v2.2 `
  --strategy four_gate `
  --bot-race protoss `
  --enemy-race terran `
  --decision-model Kimi-k2.5 `
  --data-subagent-model Kimi-k2.5 `
  --batch-name smoke
```

## Validate

Run static checks and all tests:

```powershell
python -m compileall SC2_Agent bot_loader dummies\generic tools run_vs_ai.py
python -m pytest tools\tests -q -p no:cacheprovider
```

Probe all 15 enabled strategies without launching SC2:

```powershell
python tools\probe_prompt_matrix.py `
  --decision-agent-mode data-v2.2 `
  --model-key Kimi-k2.5 `
  --enemy-race terran `
  --concurrency 5
```

The configurable SC2 sweep accepts the same `--decision-agent-mode` option.
Concurrent launches are staggered, startup is bounded, and failed jobs can be
retried.

## Records

Every match writes its interaction JSON and `*.llm_calls.json`. Naive decisions
retain schema version 2; V2.2 V1 decisions use schema version 3 and V2 planning
decisions use schema version 4. Knowledge modes record the
selected mode, MainAgent rounds, DataSubAgent sessions, model-call reasoning
flags, whether a knowledge query was used, and queue transition. A decision
may legitimately contain zero DataSubAgent sessions. Full V2.2 tool results are kept in
`knowledge_v2_2_traces/` under the match directory; V2 planning traces use the
Windows-safe compact directory `kv2_traces/`.

See [Data V2.2 decision mode](docs/data-v2.2-decision-agent.md),
[Data V2.2 V2 planning mode](docs/data-v2.2-v2-decision-agent.md),
[system architecture](docs/system-architecture.md),
[test workflow](docs/test-run-workflow.md),
[model-facing test and repair guide](test/TESTING_GUIDE.md),
[anomaly log](test/ANOMALY_LOG.md), and
[environment setup](docs/environment-setup.md).
