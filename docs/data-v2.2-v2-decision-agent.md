# Data V2.2 V2 planning decision mode

## Mode boundary

`data-v2.2-v2` is an additive planning and knowledge-utilization mode. It does
not replace or modify the preserved `naive` implementation, and it does not
modify the existing `data-v2.2` DataAgent baseline (V1). The four selectable
modes are:

- `naive`: preserved single-call decision Agent;
- `data-v2.2`: independently maintained DataAgent V1;
- `data-v2.2-v2`: planning-constrained DataAgent V2;
- `data-v2.2-v2-no-knowledge`: the same V2 planning harness with a tool-free,
  model-prior DataSubAgent control.

All modes receive the same live observation, strategy summary, trigger state,
and uncommitted queue. All return the same public `{reason, ordered_names}`
contract and use the same canonical mapper and deterministic scheduler. V2 has
its own prompts, context files, orchestration code, copied V2.2 dataset, match
ledger, and trace directory under `SC2_Agent/knowledge_v2_2_v2/`.

## V2 planning loop

Each decision derives a 15-90 second planning snapshot from the observation.
It contains current and projected minerals/gas, bank trend, supply, worker
saturation, committed assets, combat and predicted advantage, power ratio,
enemy evidence, and an air/ground engagement profile.

The snapshot produces planning targets and hard safety limits:

- a worker-addition ceiling, including an 85-worker absolute safety ceiling;
- a minimum mineral commitment when the bank is persistently high;
- total and mobile resource-to-strength investment targets;
- a gas-capacity request when minerals are high but gas income and gas
  structures cannot support the selected composition;
- required total and mobile anti-air/anti-ground response scores.

MainAgent may query DataSubAgent when evidence can change the queue. Match-local
facts are cached by query type and canonical targets. Final queues are audited
for canonical names, prerequisites, supply, resource budget, worker excess,
resource conversion, mobile strength, gas capacity, and attack-layer coverage.
The queue is capped at 20 items.

V2 now uses a four-stage harness rather than asking one model response to solve
every concern simultaneously:

1. deterministic task decomposition selects recovery, survival, verified
   counter-response, bank conversion, production expansion, economy, and
   upgrade tasks in priority order;
2. a capability gap can prefetch DataSubAgent evidence before queue generation;
3. MainAgent produces the semantic strategy queue within an estimated
   60-second production-command capacity;
4. deterministic assembly removes invalid/excess work, adds required gas and
   production capacity, fills remaining executable throughput with a legal
   race-native mobile unit, and reconciles supply.

Mineral and strength shortfalls remain observable audit metrics, but an exact
scalar mismatch no longer invalidates the whole decision. Canonical names,
prerequisites, worker ceilings, hard budgets, gas capacity, queue length, and
verified attack-layer coverage remain hard constraints. If forced-final model
output is malformed, the harness reuses and stabilizes the last contract-valid
decision instead of silently losing a decision cycle.

## Knowledge and attack-layer rules

V2 adds focused `combat_capability` evidence alongside `resource_facts`,
`enemy_counter`, `upgrade_path`, and `tech_feasibility`. The tool
`query_combat_capabilities` reads structured `Unit.weapons.target_type` fields
and returns `can_attack_air`, `can_attack_ground`, and a named engagement
matrix. `query_enemy_response_candidates` filters semantic counter relations
through the same weapon-layer gate.

A broad relation can no longer make a ground-only unit a direct anti-air
counter. For example, Roach has only a Ground weapon and is rejected as a
direct response to Battlecruiser, Liberator, or Banshee. Detection, disabling
spells, and static defenses may be useful support, but they cannot alone satisfy
the required mobile direct-fire response.

Some dataset records, including Battlecruiser, have incomplete weapon arrays.
An enemy unit with positive supply is still retained as an air/ground target;
missing weapon data only limits claims about what that unit itself can attack.

## 2026-08-03 DeepSeek validation

Configuration:

- MainAgent and DataSubAgent: `DeepSeek-V4-flash`, non-thinking;
- map: `KairosJunctionLE`;
- opponent: built-in `mediumhard`, `macro`;
- strategies: Terran `yamato_rust_fleet`, Protoss `dark_templar_rush`, Zerg
  `lurkers`;
- two matches per race, one against each of the other races, six concurrent
  matches, 60-second decisions, 1,200-second limit.

For current runs, MainAgent and DataSubAgent independently inherit reasoning
mode from their configured API profiles across every phase, including repairs
and fallback summaries. See
[reasoning-profile-routing.md](reasoning-profile-routing.md) for acceptance
criteria and treatment of historical nominal-think batches.

The first launch attempts exposed two runner defects before SC2 loaded: the
low-level CLI did not accept `data-v2.2-v2`, and difficulty keys are
case-sensitive (`mediumhard`). A later invalid batch exposed Windows path
length failure in verbose trace directories. V2 now uses `kv2_traces` and a
short trace run ID; those failed starts and path-failed matches are excluded.

The valid six-match batch is
`game_records/v2_ds4f_mh_3race_20260803_r1/`:

| Match | Result | RUR | Average bank | APU | Decisions | DataSubAgent sessions |
|---|---:|---:|---:|---:|---:|---:|
| Protoss vs Terran | Tie | 1208.8 | 5516.9 | 0.6666 | 33 | 2 |
| Protoss vs Zerg | Tie | 1296.2 | 4643.3 | 0.5036 | 29 | 3 |
| Terran vs Protoss | Defeat | 1053.6 | 4415.6 | 0.6463 | 24 | 1 |
| Terran vs Zerg | Victory | 1865.4 | 1447.3 | 0.7579 | 21 | 1 |
| Zerg vs Protoss | Tie | 1482.5 | 7385.3 | 0.8453 | 29 | 14 |
| Zerg vs Terran | Tie | 2116.2 | 5787.3 | 0.7679 | 34 | 5 |

The batch produced 170 decisions and 26 sessions. Only one match won, one lost,
and four reached the time limit. The important diagnosis was not sample win
rate: average planned mineral use was only 21%-39% of the projected horizon
budget, late banks reached 9,602-24,492 total resources, and the two Zerg games
ended at 95/56 and 124/91 workers/ideal. A semantic counter answer also listed
Roach against Terran air despite Roach having no anti-air weapon. These findings
led to the V2 constraints described above.

Final directed probes used the same model on deliberately difficult 12-minute
states with a large mineral bank, low gas, worker over-saturation, negative
combat power, and air-layer gaps. The accepted queues had no remaining audit
violations:

- Terran: no workers, Refinery plus Tank/Marine mobile conversion;
- Protoss: no workers, Assimilator plus a Stalker mobile anti-air response to
  Mutalisk/Corruptor;
- Zerg: no workers or static-defense score farming, Extractor plus eight
  Hydralisks and the Lair/Spire route against Battlecruiser/Banshee/Liberator.

The final Zerg trace is under
`game_records/prompt_probes/v2_resource_combat_deepseek_20260803_r6_zerg/`;
the final accepted Terran and Protoss traces are under the corresponding
`v2_resource_combat_deepseek_20260803_r5/` directory.

## 2026-08-04 harness regression and real matches

The next six-match batch exposed eight failed decision traces: six were in
Terran versus Zerg, one in Protoss versus Terran, and one in Zerg versus
Protoss. The main causes were mutually incompatible mineral/gas/20-item
targets, repeated forced-final JSON, worker growth during a 0-power defense
crisis, and planned unit cost without enough production throughput. That batch
ended 2 wins and 4 defeats.

The new harness replays all eight failed observations successfully: 8/8 produce
a non-empty queue with legal prerequisites, no hard budget violation, and no
remaining hard conversion or attack-layer violation. The automated V2 test
suite includes the Terran 0-power worker-throttling case, Protoss bank-to-
Gateway throughput, and Zerg gas-trim deadlock.

A same-model directed comparison used identical complex observations for
`naive`, DataAgent V1, and V2. Naive and V1 each had a hard issue in all three
races (gas capacity, excess workers, or queue overflow). V2 was clean in all
three, queried `combat_capability` before the Protoss and Zerg air responses,
and added the recommended Gateway/Hatchery throughput. Results are under
`game_records/prompt_probes/mode_compare_20260804_harness_r1/`.

The same six real matches were then repeated in
`game_records/v2_ds4f_mh_3race_20260804_harness_r2/`:

| Match | Result | RUR | Average bank | APU |
|---|---:|---:|---:|---:|
| Protoss vs Terran | Victory | 1060.3 | 479.8 | 0.6943 |
| Protoss vs Zerg | Tie | 791.2 | 1627.6 | 0.6575 |
| Terran vs Protoss | Victory | 957.0 | 1900.1 | 0.7028 |
| Terran vs Zerg | Tie | 665.0 | 689.1 | 0.6615 |
| Zerg vs Protoss | Tie | 2056.2 | 4345.7 | 0.7953 |
| Zerg vs Terran | Tie | 1545.0 | 10401.1 | 0.8009 |

The result changed from 2W/4L to 2W/0L/4T. With a tie scored as 0.5, the sample
score rose from 33.3% to 66.7%; average RUR rose from 1003.4 to 1179.1, average
bank fell from 3468.7 to 3240.6, and APU rose from 0.6665 to 0.7187. All 156 V2
traces completed successfully, compared with 8 failed traces in the preceding
batch. There were 14 DataSubAgent sessions, including 7 harness preflight
events, and 28 planned production additions.

This is a strong same-six-game regression result, not a statistical guarantee.
Zerg still accumulates a large late bank when it reaches 175-200 supply; max-
supply upgrade selection and game-closing behavior remain optimization targets.

## Commands

Run one V2 match:

```powershell
python tools\run_experiment.py `
  --decision-agent-mode data-v2.2-v2 `
  --decision-model DeepSeek-V4-flash `
  --data-subagent-model DeepSeek-V4-flash `
  --strategy lurkers `
  --bot-race zerg `
  --enemy-race terran `
  --enemy-difficulty mediumhard
```

Run the three directed resource/combat probes:

```powershell
python tools\probe_v2_resource_combat_scenarios.py `
  --model-key DeepSeek-V4-flash
```

Use the same scenarios for a mode comparison by adding one of
`--decision-agent-mode naive`, `data-v2.2`, or `data-v2.2-v2`.

V2 match decisions use schema 4 and store full per-decision traces under
`<match>/kv2_traces/`. `knowledge_query_used` counts new DataSubAgent sessions;
cache reuse is recorded separately.

The no-knowledge control design and same-six-match result are documented in
[data-v2.2-v2-no-knowledge.md](data-v2.2-v2-no-knowledge.md).
