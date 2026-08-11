# Test and run workflow

## 1. Static verification

From the repository root:

```powershell
python -m compileall SC2_Agent bot_loader dummies\generic tools run_vs_ai.py
python -m pytest tools\tests -q -p no:cacheprovider
git diff --check
```

In addition to the scheduler and original decision tests, the V2.2 tests
verify:

- supported launchers, `GameStarter`, and the low-level bot all default to
  `data-v2.2`, while `data-v2.2-v2`, `data-v2.2-v2-no-knowledge`, `data-v2.3`, and `naive`
  remain explicitly selectable;
- the new prompt contains the original event context and separately maintained
  data/subagent guidance;
- MainAgent can finalize directly or choose a DataSubAgent session;
- MainAgent and DataSubAgent model keys route independently;
- the internal orchestration and public decision contracts reject malformed
  responses;
- all query imports resolve to the vendored package and data;
- copied build checksums match `COPY_MANIFEST.json`;
- every allowed macro name exists in the local dataset;
- tool catalog, dispatcher, argument schemas, compact evidence references, and
  expansion stay synchronized;
- all V2.2 prompt and static context files remain English ASCII.
- the no-knowledge DataSubAgent uses a direct-answer prompt, receives no tools,
  emits no observations, and marks database access false while MainAgent
  wording and V2 queue assembly stay shared with `data-v2.2-v2`.
- V2.3 rejects provider-native tools, executes repository queries locally,
  sends DataSubAgent one ordinary text completion, preserves deterministic
  evidence on summary failure, and continues safely when retrieval fails.

## 2. Model configuration

`API_config/config.json` is ignored by Git. Configure `Kimi-k2.5` with the
test environment's endpoint and credential, `is_reasoning: false`,
`reasoning_extract_mode: "none"`, and both provider thinking switches disabled.
Never print or commit the credential.

Check the effective response path before launching SC2:

```powershell
python API_Tools\probe_reasoning_extraction.py `
  --model-key Kimi-k2.5 `
  --max-tokens 256
```

Expected: `is_reasoning` is false, `reasoning_length` is zero, and there is no
provider error.

V2.2 applies a cross-process Kimi rate limit before every MainAgent and
DataSubAgent call. Its default is 50 requests per rolling minute. Set
`SC2_KIMI_RPM` only when the actual provider quota differs.

## 3. Prompt matrix

Probe the real mode-specific orchestration across all 15 enabled strategies
without launching SC2:

```powershell
python tools\probe_prompt_matrix.py `
  --decision-agent-mode data-v2.2 `
  --model-key Kimi-k2.5 `
  --subagent-model-key Kimi-k2.5 `
  --enemy-race terran `
  --concurrency 5 `
  --output game_records\prompt_probes\data_v2_2_kimi_15.json
```

Every result must parse to the exact public contract. Fail the gate if any
result has a provider error, rejected response, unknown canonical name, or
unmapped canonical name. To compare the preserved baseline, rerun with
`--decision-agent-mode naive`.

## 4. Short SC2 smoke match

```powershell
python tools\run_experiment.py `
  --decision-agent-mode data-v2.2 `
  --strategy marine_rush `
  --bot-race terran `
  --enemy-race terran `
  --enemy-difficulty easy `
  --enemy-build macro `
  --decision-model Kimi-k2.5 `
  --data-subagent-model Kimi-k2.5 `
  --decision-interval 60 `
  --game-time-limit 360 `
  --batch-name data_v2_2_smoke
```

The preserved launcher and Sharpy lifecycle are used, so this checks real
startup, decisions, mapping, queue replacement, scheduler execution, result
JSON, and Replay creation.

## 5. Full-match release gate

A short timeout tie is not the final release criterion. Run at least one match
long enough to reach a natural result:

```powershell
python tools\run_experiment.py `
  --decision-agent-mode data-v2.2 `
  --strategy four_gate `
  --bot-race protoss `
  --enemy-race terran `
  --enemy-difficulty easy `
  --enemy-build macro `
  --decision-model Kimi-k2.5 `
  --data-subagent-model Kimi-k2.5 `
  --decision-interval 60 `
  --game-time-limit 1200 `
  --batch-name data_v2_2_long_regression
```

Review a recoverable scheduler warning in context; it is not automatically an
agent failure. A decision exception, trace failure, provider error, unknown or
unmapped name, or missing match result is a release failure.

## 6. What to inspect

Under `game_records/<batch>/<match>/`, inspect the match JSON,
`*.llm_calls.json`, log, Replay, and the mode-specific trace directory
(`knowledge_v2_2_traces/` for V1 or `kv2_traces/` for V2).
The no-knowledge control uses `kv2_no_knowledge_traces/`.

Expected for `data-v2.2`:

- every decision record has `decision_agent_mode: "data-v2.2"` and schema 3;
- output is `reason` plus accepted, mapped `ordered_names`;
- `knowledge_query_used` agrees with whether DataSubAgent sessions exist;
- zero sessions is valid when MainAgent finalized directly;
- every session that was opened, and every trace, finishes successfully;
- every model call has `is_reasoning: false`, no provider reasoning, and no
  error when testing Kimi non-thinking;
- unknown and unmapped names are empty;
- calls occur at initial, interval, or drain triggers only;
- already issued work is absent from the old-uncommitted list;
- the new queue records carried, discarded, and introduced names;
- a parseable natural game result and Replay exist.

For `data-v2.2-v2`, additionally require schema 4, a successful final queue
audit, no hard worker/queue/resource/capability violation, an explicit task
decomposition and production-capacity estimate, and a verified
`combat_capability` session or cache fact whenever the attack-layer profile
reports an air or ground gap. Mineral/strength target shortfalls are measured
but do not by themselves discard an otherwise executable decision. See
`docs/data-v2.2-v2-decision-agent.md` for the 2026-08-03 and 2026-08-04 DeepSeek
experiments, mode comparison, and directed probes.

For `data-v2.2-v2-no-knowledge`, apply the same V2 queue gates and additionally
require every session to have `selected_tools: []`, `observations: []`,
`answer_source: "model_prior"` (or `"model_prior_cache"`),
`knowledge_database_access: false`, and no tool request/response event.
`knowledge_query_used` must remain false even when the tool-free DataSubAgent
was used. The SubAgent system prompt may differ from V2, but MainAgent prompts
and focused questions must remain aligned. The deterministic dataset-load event
is expected because the V2 planner/auditor remains data-backed. See
`docs/data-v2.2-v2-no-knowledge.md`.

Useful search:

```powershell
rg -n -i `
  'Traceback|decision_error|provider_error|unknown_names|unmapped_names|is_reasoning|Abandoned stuck RUNNING' `
  game_records\<batch>\<match>
```

Raw query results can be large and intentionally live only in each trace. The
main match and call-summary files should contain orchestration metadata rather
than duplicate tool payloads.

For thinking/non-thinking comparisons, validate every applicable role rather
than trusting the batch name. `configured_model_key`, resolved `model_key`,
`profile_reasoning_mode`, `reasoning_requested`, and returned `is_reasoning`
must agree. V1/V2 MainAgent repairs and DataSubAgent selection/summary calls
inherit their role profile. Only the no-knowledge SubAgent is intentionally
forced non-thinking. Historical knowledge batches with
`reasoning_requested: false` are non-thinking data even when named `think`.
See [reasoning-profile-routing.md](reasoning-profile-routing.md).

## 7. Failure semantics

- A malformed naive response or one with no mappable names leaves the old
  local queue unchanged.
- A valid empty public queue clears local uncommitted work and waits for the
  next interval.
- A V1 orchestration error is recorded and never switches to the naive prompt.
  V2 first stabilizes the last contract-valid queue with its deterministic
  harness; only an unrecoverable hard constraint or provider failure is
  recorded as an orchestration error.
- A valid replacement discards old uncommitted local work, while work already
  issued to SC2 continues in the engine.

## 8. Sweep

Dry-run, then launch a small matrix:

```powershell
python tools\run_kimi_nothink_strategy_sweep.py `
  --decision-agent-mode data-v2.2 `
  --dry-run

python tools\run_kimi_nothink_strategy_sweep.py `
  --decision-agent-mode data-v2.2 `
  --decision-model Kimi-k2.5 `
  --data-subagent-model Kimi-k2.5 `
  --strategies marine_rush,bio `
  --bot-races terran `
  --enemy-races terran `
  --difficulties medium `
  --maps KairosJunctionLE `
  --repeats 1 `
  --concurrency 1
```

Concurrent launches are staggered and each child is naturally awaited. Confirm
each child reaches `Status.in_game`, but count a result only when the artifact
is parseable, engine-reported, and free of timeout/watchdog, process-exit,
API, and reasoning-policy errors. Retry only failed conditions and report
retries, ties, terminal failures, and missing results separately from win rate.
The full acceptance boundary is
[`SC2_BATCH_EXPERIMENT_POLICY.md`](SC2_BATCH_EXPERIMENT_POLICY.md).

For a reusable multi-group comparison, use the versioned configuration layer:

```powershell
python tools\run_experiment_config.py `
  --config experiment_configs\templates\matrix450-three-mode.example.json `
  --validate
```

Copy the chosen template into ignored `experiment_configs/local/`, assign
unique real batch names, dry-run it, and then execute it. The loader reports
the expanded job count before launch and the runner writes a resolved manifest.
See [experiment-configuration.md](experiment-configuration.md). Long ad-hoc CLI
commands remain supported for small diagnostics, but are not the authoritative
record of a formal comparison.

## 9. Recorded integration result

On 2026-08-02, the optional-query and split-provider revision completed with
88 tests passing and one 360-second real match for each race. Terran and
Protoss reached the time limit, Zerg won at 05:33, and all 22 decisions had
zero decision, provider, reasoning, unknown, mapping, or scanned log errors.
All 22 routine decisions finalized directly. A separate knowledge-critical
probe opened one DataSubAgent session and verified role/model-key routing
before MainAgent finalized on round two. The earlier full Protoss victory at
09:50 remains the natural-result integration gate. Detailed evidence is in
`docs/data-v2.2-decision-agent.md`.

Current V2 testing and paired knowledge/no-external-knowledge trace analysis start
from `test/README.md`. The earlier model-facing repair procedure and anomaly log
are frozen under `test/archive/2026-07-legacy-agent-validation/` for historical
reproduction only.
