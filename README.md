# SC2-Agent Knowledge

This branch runs one summary-guided macro decision agent for Terran.

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

## Strategy files

Strategies live under:

```text
SKILL/terran/<strategy>/Top_agent_<enemy_race>.md
```

Each file contains only `# Summary`. There are no per-step instructions. The
summary is injected into every macro decision.

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
  --decision-model Kimi-k2.5 `
  --decision-interval 60 `
  --batch-name smoke
```

Both commands continue through the existing `bot_loader`/Sharpy startup path.
The agent-specific CLI has only one model option, `--decision-model`.

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
and [environment setup](docs/environment-setup.md).
