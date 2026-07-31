# Current system architecture

## 1. Scope

The runtime has one LLM responsibility: periodically produce a complete,
ordered macro queue in canonical names for Terran, Protoss, or Zerg. Naming and ordering are one
operation. Concrete execution is code-owned.

There is no:

- Naming Agent;
- Ordering Agent;
- Ordered Naming mode switch;
- Executor LLM;
- Supply Planner;
- BO-list execution mode;
- per-step strategy instruction.

This scope does not remove or rewrite Sharpy itself. `sharpy/`, `python-sc2/`,
the non-LLM bots in `dummies/`, `bot_loader/`, and ladder/general-purpose
scripts remain in the repository. The new architecture applies to
`dummies/generic/universal_llm_bot.py` and the `SC2_Agent/` modules it uses.

## 2. End-to-end flow

```text
Top_agent.md: # Summary
                 +
current structured/text observation
                 +
uncommitted canonical names from previous queue
                 │
                 ▼
SC2_Agent/decision_agent.py
                 │
        {reason, ordered_names}
                 │
                 ▼
data_tools canonical validation and entity-to-action mapping
                 │
        valid response?
          ├─ no: retain old local queue
          └─ yes
                 │
                 ▼
ExecutionScheduler.replace_uncommitted_queue()
                 │
                 ▼
priority scan, waiter, prerequisite/resource gates,
skip/overtake, deterministic producer/worker selection
                 │
                 ▼
SC2 simulation engine
```

## 3. Trigger rules

`UniversalLLMBot.pre_step_execute()` evaluates the trigger every frame.

1. `initial_decision`: first decision after startup.
2. `interval_elapsed`: default 60 in-game seconds after the previous attempt.
3. `queue_drained`: an accepted non-empty queue transitions from active to
   fully terminal, with a five-second anti-loop guard.

`queue_drained` means every scheduler task and the separate waiter are
terminal. A queue with one uncommitted task is not drained and does not trigger
early replanning. An accepted empty queue marks that cycle as having no work;
it cannot cause an immediate drain loop and waits for `interval_elapsed`.

The interval is measured in game time, not wall-clock time.

## 4. Prompt and output

`SC2_Agent/decision_agent.py` builds one system message with ten stable
sections:

1. agent role and responsibility boundary;
2. decision lifecycle;
3. queue and commitment semantics;
4. selected-race identity and mechanics;
5. economy, supply, worker, and bank-spending principles;
6. the selected strategy objective from `Top_agent.md`;
7. script-owned strategy automation behavior;
8. observation field definitions;
9. exact allowed canonical macro outputs;
10. the JSON response contract.

The separate user message is event state, not another policy prompt. It
contains:

- decision cycle and trigger reason;
- current in-game time and configured interval;
- enemy race;
- the latest text observation;
- previous queue names that are not committed yet;
- an explicit reminder that accepting the answer replaces those names.

The observation guide distinguishes supply used/cap/free, worker
current/ideal, army supply, income rates, committed work under construction or
en route, active engine queues, remembered enemy intelligence, combat power,
losses, completed research, and threat flags. This avoids treating descriptive
fields or engine action keys as canonical macro vocabulary.

The unfinished section contains only an ordered JSON array of canonical names.
It deliberately omits status, action keys, quantities, producers, and metadata.
Repeated names represent repeated requested copies.

The model is told that accepting this decision discards the listed old local
work. It must repeat any still-important old item in the new queue and may omit
items it wants to abandon. It must inspect the observation to avoid recreating
work already submitted to the engine.

Output:

```json
{
  "reason": "Concise public decision explanation.",
  "ordered_names": ["SupplyDepot", "Barracks", "Marine", "Marine"]
}
```

The model plans only the near-term horizon before the next decision and is
asked to keep the queue compact, normally no more than 20 names. This prevents
the summary from being expanded into a full-game build order every minute.

`reason` is persisted for auditing but is not chain-of-thought. Empty
`ordered_names` is legal. A malformed response, or a non-empty response for
which no name can be mapped, leaves the old queue unchanged.

Unknown or individually unmappable names are recorded and dropped. If at least
one valid task remains, the valid mapped queue is accepted.

## 5. Queue replacement and commit boundary

`issued_count` is the boundary between local intent and engine-owned work.

- `quantity - issued_count` copies are uncommitted, cancellable, and eligible
  to appear in the next prompt.
- Once a command has been issued, it belongs to the SC2 simulation. Replanning
  does not cancel it, hide it from the game state, or attempt to recover it into
  the new local queue.
- Research crosses the same commit boundary as soon as its matching ability is
  present in a structure's active orders. It does not wait for the upgrade to
  finish before disappearing from the uncommitted prompt list.

On an accepted decision the scheduler:

1. snapshots the old uncommitted canonical names;
2. releases local Act/worker/reservation handles;
3. removes the old action list and waiter;
4. creates one `PlannedAction` per new canonical name, retaining queue id and
   position;
5. starts executing the new queue.

This is an atomic replacement of local scheduler state. It is not append,
merge, or automatic deduplication.

## 6. Execution scheduler

The scheduler keeps the established skip/overtake model:

- one independent waiter for the currently blocked action;
- one ordered scan in the exact sequence produced by the model;
- later tasks may overtake a blocked earlier task when they do not spend
  resources reserved for the waiter;
- supply-providing tasks are not globally moved ahead of the model order;
- prerequisites are checked against runtime state and are not silently added.

Normal Terran structures use `DirectBuildExecutor` where supported. Race-aware
build, gas, expansion, research, add-on, and morph actions use Sharpy Acts.
Train and morph actions use
`producer_selector.py`, which deterministically prefers idle producers, then
shorter order queues, then stable unit tag order. No LLM is called to choose a
producer or worker. Gateway training can switch to powered WarpGate placement,
Archon morphing combines two Templars, and Zerg production uses the live
Larva/Drone action surface.

Research is considered committed as soon as `BotAI.already_pending_upgrade`
reports progress, even when the reviewed action name and the engine's generic
research ability name differ. Gas-building requests remain waiting when no
completed base has a free geyser instead of being discarded by the generic
running-action timeout.

The scheduler also enforces conservative caps for non-production technology
structures. Unique Protoss and Zerg technology structures stop at one, while
Forge and EvolutionChamber stop at two. Production structures such as Gateway,
Stargate, RoboticsFacility, and Hatchery remain uncapped and are scaled by the
selected strategy.

There is no automatic supply-provider insertion. `supply_left` is still used
by the resource gate so impossible train commands wait, but the model must
place `SupplyDepot`, `Pylon`, or `Overlord` in its own queue.

## 7. Strategy knowledge

`SC2_Agent/top_agent.py` parses only the text under `# Summary`. The selected
file is:

```text
SKILL/<our_race>/<strategy>/Top_agent.md
```

The same complete summary is provided at every decision. Each enabled
`strategy_tools.py` exports one `AUTOMATION_PROFILE`. Its attack threshold and
optional gate configure both the real tactical plan and the human-readable
prompt context. Defense, rallying, scouting, race utilities, and special
behaviors are also rendered from that profile. It is not a second macro
planner.

`SC2_Agent/strategy_registry.py` reads `SKILL/<race>/registry.json`. Exactly
five representative strategies are enabled for each race. Retained but
uncurated folders are rejected at the run boundary instead of silently loading
an empty tactical configuration.

| Race | Enabled strategies |
|---|---|
| Terran | `marine_rush`, `bio`, `blueflame_locks`, `two_base_matrix_tanks`, `yamato_rust_fleet` |
| Protoss | `four_gate`, `dark_templar_rush`, `robo`, `voidray`, `macro_stalkers` |
| Zerg | `twelve_pool`, `macro_roach`, `roach_hydra`, `lurkers`, `mutalisk` |

## 8. Record schema

The main interaction stream uses `schema_version: 2`. A decision record stores:

```json
{
  "cycle": 2,
  "trigger_reason": "interval_elapsed",
  "old_uncommitted_canonical_names": ["Barracks", "Marine"],
  "decision": {
    "reason": "Keep production growing while covering supply.",
    "ordered_names": ["SupplyDepot", "Barracks", "Marine"],
    "accepted_ordered_names": ["SupplyDepot", "Barracks", "Marine"],
    "mapped_actions": []
  },
  "queue_transition": {
    "carried_forward_names": ["Barracks", "Marine"],
    "discarded_old_names": [],
    "newly_introduced_names": ["SupplyDepot"]
  },
  "committed_work_untouched": true
}
```

The companion `*.llm_calls.json` has one `agent: "macro_decision"` entry per
model call. `decision_reason` is the public response field. Any provider-side
reasoning is stored separately as `provider_reasoning`; in Kimi non-thinking
mode it should be empty and `is_reasoning` should be false.

## 9. Main files

| File | Responsibility |
|---|---|
| `dummies/generic/universal_llm_bot.py` | trigger, prompt call, validation, replacement, records |
| `SC2_Agent/decision_agent.py` | sole model prompt and response parser |
| `SC2_Agent/prompt_context.py` | lifecycle, observation guide, and shared strategy automation profiles |
| `SC2_Agent/strategy_registry.py` | five-per-race production strategy gate |
| `SC2_Agent/top_agent.py` | summary-only strategy parser |
| `SC2_Agent/data_tools/entity_to_actions.py` | canonical name to action mapping |
| `SC2_Agent/execution/scheduler.py` | queue state and deterministic execution |
| `SC2_Agent/execution/producer_selector.py` | deterministic train producer selection |
| `SC2_Agent/execution/command.py` | `PlannedAction` including queue identity |
| `bot_loader/game_starter.py` | preserved Sharpy launcher with current agent options |
| `run_vs_ai.py` | supported agent match CLI built on the existing bot loader |
| `tools/probe_prompt_matrix.py` | no-engine output-contract probe across all 15 enabled strategies |
| `tools/run_kimi_nothink_strategy_sweep.py` | retryable, staggered multi-race SC2 matrix runner |

## 10. Batch startup behavior

The sweep runner starts children with unbuffered UTF-8 output, writes and
flushes the attempt command before launch, and enforces a configurable minimum
gap between concurrent SC2 launches. `SC2_STARTUP_TIMEOUT` bounds websocket
startup. The bundled `SC2Process` checks whether the client has already exited
and reports its return code immediately; a live client that never publishes
the websocket receives a precise timeout error. Failed jobs are retried by the
sweep runner and are not counted as valid merely because a directory exists.

## 11. Retained versus removed code

Retained:

- Sharpy and bundled python-sc2 framework code;
- all original demo/race bots and their bot definitions;
- ladder, packaging, map, and general run scripts;
- deterministic execution code required to turn canonical names into SC2
  commands;
- strategy-specific tactical/background `strategy_tools.py`.

Removed:

- separate Naming, Ordering, and Executor model agents;
- automatic Supply Planner and prerequisite gap-fill insertion;
- BO-list execution mode and its duplicated strategy data;
- launchers, tests, and archives whose only purpose was configuring those
  removed stages.
