# Test and run workflow

## 1. Static verification

From the repository root:

```powershell
python -m py_compile `
  SC2_Agent\decision_agent.py `
  SC2_Agent\execution\scheduler.py `
  SC2_Agent\execution\producer_selector.py `
  bot_loader\game_starter.py `
  dummies\generic\universal_llm_bot.py `
  run_vs_ai.py
```

Run tests:

```powershell
python -m pytest tools\tests -q
```

The decision-specific tests verify:

- exact JSON response parsing, including an empty queue;
- prompt replacement semantics and unmanaged supply;
- 60-second and queue-drained triggers;
- no early trigger when one item remains;
- no empty-queue retrigger loop;
- only uncommitted copies appear in prompt order;
- a research item disappears from that list as soon as the corresponding
  research order has been accepted by the SC2 engine;
- deterministic producer selection;
- every strategy markdown file is summary-only.

The smoke run uses the preserved `bot_loader` and Sharpy lifecycle, so it also
checks that the refactored agent still starts through the repository's normal
bot infrastructure.

## 2. Model configuration

`API_config/config.json` is ignored by Git. Add a `Kimi-k2.5` model profile
with:

- the endpoint and credential supplied for the test environment;
- `model_name: "kimi-k2.5"`;
- `is_reasoning: false`;
- `reasoning_extract_mode: "none"`;
- non-reasoning temperature `0.6`;
- both provider thinking switches disabled.

Do not print the credential in logs or commit the config file.

## 3. Non-thinking smoke match

Recommended first match:

```powershell
$env:SC2_GAME_TIME_LIMIT='240'
python tools\run_experiment.py `
  --strategy marine_rush `
  --decision-model Kimi-k2.5 `
  --decision-interval 60 `
  --enemy-race terran `
  --enemy-difficulty medium `
  --map-name KairosJunctionLE `
  --batch-name kimi_nothink_queue_smoke
```

The standalone battle-cruiser wrapper is:

```powershell
python tools\run_kimi_nothink_bc.py
```

## 4. What to inspect

Under `game_records/<batch>/<match>/`, inspect the normal JSON and
`*.llm_calls.json`.

Expected:

- `agent` is always `macro_decision`;
- `model_key` is `Kimi-k2.5`;
- `is_reasoning` is false;
- `provider_reasoning` is empty;
- output parses to `reason` plus `ordered_names`;
- calls occur initially and then at interval/drain triggers;
- prompt unfinished tasks contain canonical names only;
- a new queue records carried/discarded/introduced names;
- already issued work is not copied into unfinished tasks;
- model includes its own `SupplyDepot` when needed.

Useful PowerShell search:

```powershell
Get-ChildItem game_records\kimi_nothink_queue_smoke -Recurse -Filter *.json |
  Select-String -Pattern 'macro_decision|trigger_reason|decision_reason|provider_reasoning|old_uncommitted'
```

## 5. Failure rules

- Invalid JSON or missing `reason`/`ordered_names`: old local queue must remain.
- A non-empty response with no mappable tasks: old local queue must remain.
- Valid empty queue: old local queue is cleared; next decision waits for the
  interval.
- Valid replacement: old uncommitted local work disappears immediately, while
  work already issued to SC2 continues in the simulation.

## 6. Sweep

Dry-run the matrix without launching SC2:

```powershell
python tools\run_kimi_nothink_strategy_sweep.py --dry-run
```

Run a small sweep:

```powershell
python tools\run_kimi_nothink_strategy_sweep.py `
  --decision-model Kimi-k2.5 `
  --decision-interval 60 `
  --strategies marine_rush,bio `
  --maps KairosJunctionLE `
  --enemy-races terran `
  --difficulties medium `
  --repeats 1 `
  --concurrency 1
```
