# Data V2.2 decision-agent mode

## Purpose and compatibility

`data-v2.2` is the default decision mode for the supported launchers. It keeps
the existing observation, trigger, canonical action vocabulary, queue
replacement semantics, deterministic scheduler, and public decision contract.
Only the model-side decision implementation changes.

The original implementation remains available as `naive` and its source file,
`SC2_Agent/decision_agent.py`, is not shared with or modified by the V2.2
implementation. The two modes maintain separate prompts and parsers.

```text
same decision event context
          │
          ├─ naive ─────── SC2_Agent/decision_agent.py
          │
          └─ data-v2.2 ── MainAgent
                              │ ask_subagent
                              ▼
                         DataSubAgent
                              │ native tool calls
                              ▼
                    local SC2 V2.2 dataset
                              │ evidence answer
                              ▼
                         MainAgent
                              │
                              ▼
                   {reason, ordered_names}
```

Both branches return the same public result:

```json
{
  "reason": "Concise public decision explanation.",
  "ordered_names": ["Pylon", "Gateway", "Stalker"]
}
```

The normal canonical-name validator and entity-to-action mapper run after this
result. Data entities that are informative but not executable cannot enter the
scheduler.

## Local V2.2 package

The integration is self-contained under `SC2_Agent/knowledge_v2_2/`. It does
not import runtime code or data from the sibling `SC2_DATA_Agent` checkout.
The copied dependency closure includes:

- MainAgent and DataSubAgent orchestration;
- contracts, runtime adapter, trace writer, model-view compaction, and rate
  limiter;
- query engine, tool registry, and search tools;
- the complete `data_sc2_260701` build, including SQLite data, relations, and
  Markdown evidence;
- source provenance and SHA-256 checksums in `COPY_MANIFEST.json` and
  `UPSTREAM.md`.

The copied dataset contains 683 abilities, 204 units, 124 upgrades, 109
sub-ontologies, 6,503 relations, and 116 Markdown evidence files. All currently
allowed Terran, Protoss, and Zerg macro names are present in it.

## Context and interaction contract

The V2.2 MainAgent receives the same decision-event information as the naive
agent:

- selected strategy summary and script-owned automation description;
- our race, enemy race, decision cycle, trigger, game time, and interval;
- the complete current observation;
- the previous queue's uncommitted canonical names;
- the exact race-specific executable-name allowlist and replacement rules.

Its separately maintained context also explains the dataset's entity and
relation shapes, field meanings, evidence references, query boundaries, and
how to ask DataSubAgent focused questions. MainAgent decides whether a query is
needed: it may finalize immediately for a routine, sufficiently supported
decision, or ask focused questions when an uncertain static fact could
materially change the queue. Each DataSubAgent session is fresh and can use
native model tool calls against only the vendored data.

MainAgent's internal response is either `ask_subagent` or `final_decision`.
This internal contract is not exposed to the game scheduler. A malformed or
unfinished orchestration is an agent error; it does not silently fall back to
the naive prompt.

## Runtime, rate limiting, and records

Both agents use the repository's configured model caller, but MainAgent and
DataSubAgent receive independent model keys. Each key may point to a different
`api_url`, credential, and model in `API_config/config.json`. Both defaults are
currently `Kimi-k2.5` with reasoning disabled. The V2.2 package has its own
per-call rate limiter and trace storage. Kimi calls default to 50
requests per rolling minute. Override that limit only when the provider quota
permits it:

```powershell
$env:SC2_KIMI_RPM='50'
```

Run either mode explicitly:

```powershell
python tools\run_experiment.py `
  --decision-agent-mode data-v2.2 `
  --decision-model Kimi-k2.5 `
  --data-subagent-model Kimi-k2.5 `
  --strategy four_gate `
  --bot-race protoss `
  --enemy-race terran `
  --decision-model Kimi-k2.5

python tools\run_experiment.py `
  --decision-agent-mode naive `
  --strategy four_gate `
  --bot-race protoss `
  --enemy-race terran `
  --decision-model Kimi-k2.5
```

The supported launchers, `GameStarter`, and the low-level `UniversalLLMBot`
constructor default to `data-v2.2`, so the knowledge-backed agent fully
replaces the normal decision path. Existing direct callers can still select
the preserved implementation explicitly with `decision_agent_mode="naive"`.

V2.2 match decision records use schema version 3 and include
`decision_agent_mode` plus orchestration metadata. It explicitly records
`knowledge_query_used` and both model keys; zero subagent sessions is valid.
The companion
`*.llm_calls.json` summarizes MainAgent decisions, DataSubAgent sessions, and
all model calls. Full deterministic tool results remain in the per-decision
trace under `<match>/knowledge_v2_2_traces/`; they are not duplicated into the
main match record.

## Verified Kimi non-thinking evidence

The current optional-query and split-provider implementation was validated on
2026-08-02 with `Kimi-k2.5` configured as non-reasoning:

- reasoning extraction probe passed with no reasoning content;
- 88 automated tests passed, including direct-final and separate-provider
  routing tests;
- one 360-second match ran for each race: Terran `marine_rush` tied at the time
  limit with 7 decisions, Protoss `four_gate` tied at the time limit with 9,
  and Zerg `twelve_pool` won at 05:33 with 6;
- all 22 match decisions legitimately finalized without a knowledge query and
  had zero decision, provider, reasoning, unknown-name, mapping, or scanned log
  errors;
- a targeted Mutalisk-threat probe caused MainAgent to choose one DataSubAgent
  session, then finalize on round two. Its 9 model calls carried the correct
  `main_agent` and `data_subagent` roles and were all non-reasoning.

The three-race artifacts are under
`game_records/data_v2_2_optional_query_three_race/`; the targeted-query trace is
under `game_records/prompt_probes/optional_query_targeted/`.

The earlier full-match gate remains valid: Protoss `four_gate` versus Easy
Terran completed in victory at 09:50 with zero decision, unknown-name, or
mapping errors. Its artifacts are under
`game_records/data_v2_2_long_regression/20260802_190307_kv22full/`.

One existing
scheduler recovery path abandoned a ShieldBattery worker-build action after
its 25-second confirmation window; it released the stuck local task as
designed, did not indicate an agent or mapping failure, and the match continued
to victory.
