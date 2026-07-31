# SC2-Agent Knowledge

This branch runs one summary-guided macro decision agent for Terran, Protoss,
and Zerg.

```text
strategy summary + current observation + previous uncommitted canonical names
                               │
                               ▼
                      Macro Decision LLM
                   { reason, ordered_names }
                               │
                               ▼
                  canonical name → SC2 action
                               │
                               ▼
              deterministic ExecutionScheduler
```

The LLM does not choose a worker or production structure. It produces one
complete replacement queue of canonical names. The runtime owns prerequisite
checks, resource reservation, skip/overtake behavior, producer selection, and
command submission.

## Repository boundary

This branch changes only the `UniversalLLMBot` macro-planning path. The
repository's original Sharpy infrastructure is intentionally retained:

- `sharpy/` and the bundled `python-sc2/`;
- the example bots under `dummies/`;
- `bot_loader/`, ladder launchers, and general run/packaging scripts.

`dummies/generic/universal_llm_bot.py` is the bot wired to the new
`SC2_Agent` decision runtime. Other Sharpy bots remain available as examples
and independent launch targets; they are not part of this agent's decision
pipeline.

## Decision semantics

A decision is requested:

- once at the beginning;
- every 60 in-game seconds by default;
- when a non-empty queue becomes fully drained, subject to a short anti-loop
  guard.

If one task remains, the queue is not considered drained, so the next decision
waits for the normal interval. An accepted empty queue is valid and also waits
for the interval.

The prompt lists only the previous queue's canonical names that have not yet
been submitted to the SC2 simulation. The new `ordered_names` list replaces all
of those local tasks. Important old work must therefore be repeated by the
model. Commands already submitted to SC2 are never cancelled or shown in this
list.

The response contract is:

```json
{
  "reason": "Public, concise explanation; not chain-of-thought.",
  "ordered_names": ["SupplyDepot", "Barracks", "Marine"]
}
```

The queue is a compact near-term horizon, normally no more than 20 names; it is
not a full-game build order.

`SupplyDepot` is not inserted automatically. Supply planning is part of the
model's queue.

## Prompt structure

The system prompt is assembled as ten explicit sections:

1. agent role and responsibility boundary;
2. decision lifecycle;
3. queue and commitment semantics;
4. race identity and mechanics;
5. economy and production principles;
6. strategy objective;
7. automated strategy behaviors;
8. observation field guide;
9. allowed canonical macro outputs;
10. JSON response contract.

The user message supplies the decision cycle, trigger reason, in-game time,
configured interval, enemy race, latest observation, and the previous queue's
uncommitted canonical names. The previous explanation and completed queue
history are not carried forward.

Race context describes the race's shared mechanics, strengths, costs, and
planning implications. Strategy automation context describes the exact
script-owned attack threshold and any composition/technology gate, plus
defense, rallying, scouting, race utilities, and special tactical behavior.
The model therefore requests only macro production, construction, morph, and
research work; deterministic scripts own execution, combat, and micro.

## Strategy files

Strategies for every supported race live under:

```text
SKILL/<our_race>/<strategy>/Top_agent.md
```

Each strategy directory contains exactly one opponent-agnostic Markdown file
with only `# Summary`. There are no per-step instructions. The summary is
injected into every macro decision. Its `strategy_tools.py` exports an
`AUTOMATION_PROFILE`; the same object configures the real attack behavior and
renders the model-facing automation description, preventing threshold drift.

Only five representative strategies per race are enabled:

| Race | Enabled strategies |
|---|---|
| Terran | `marine_rush`, `bio`, `blueflame_locks`, `two_base_matrix_tanks`, `yamato_rust_fleet` |
| Protoss | `four_gate`, `dark_templar_rush`, `robo`, `voidray`, `macro_stalkers` |
| Zerg | `twelve_pool`, `macro_roach`, `roach_hydra`, `lurkers`, `mutalisk` |

The source of truth is `SKILL/<race>/registry.json`. Other strategy folders are
retained for later curation but production launchers reject them explicitly;
there is no empty-strategy fallback.

## Run

Configure a model key in the ignored `API_config/config.json`, then:

```powershell
python run_vs_ai.py `
  --decision-model Kimi-k2.5 `
  --decision-interval 60 `
  --force-strategy marine_rush `
  --enemy-race terran `
  --enemy-difficulty medium
```

For one explicit experiment:

```powershell
python tools/run_experiment.py `
  --strategy marine_rush `
  --bot-race terran `
  --decision-model Kimi-k2.5 `
  --decision-interval 60 `
  --batch-name smoke
```

Both commands continue through the existing `bot_loader`/Sharpy startup path.
The agent-specific CLI has only one model option, `--decision-model`.

## Validate prompts and matches

Probe all 15 enabled strategies without launching SC2:

```powershell
python tools/probe_prompt_matrix.py `
  --model-key Kimi-k2.5 `
  --enemy-race terran `
  --concurrency 5
```

Run a configurable SC2 sweep:

```powershell
python tools/run_kimi_nothink_strategy_sweep.py `
  --strategies enabled `
  --bot-races terran,protoss,zerg `
  --enemy-races terran,protoss,zerg `
  --difficulties easy,medium,mediumhard `
  --maps KairosJunctionLE `
  --enemy-build macro `
  --repeats 2 `
  --concurrency 5
```

Concurrent launches are staggered by default. Each child uses unbuffered logs,
and the SC2 websocket startup timeout is configurable. A client that exits
before publishing its websocket fails immediately so the sweep can retry it
instead of waiting for the full timeout.

## Records

Each match writes its normal interaction JSON and a companion
`*.llm_calls.json`. Decision records use schema version 2 and include:

- trigger reason and interval;
- strategy summary and observation;
- old uncommitted canonical names;
- public `reason` and accepted `ordered_names`;
- canonical-name-to-action mapping;
- carried, discarded, and introduced names;
- provider reasoning separately, if a provider returned any.

See [system architecture](docs/system-architecture.md), [test workflow](docs/test-run-workflow.md),
[model-facing test and repair guide](test/TESTING_GUIDE.md),
[anomaly log](test/ANOMALY_LOG.md), and
[environment setup](docs/environment-setup.md).
