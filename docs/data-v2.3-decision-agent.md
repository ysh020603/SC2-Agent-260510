# DataAgent V2.3: portable, evidence-gated knowledge use

## Purpose

`data-v2.3` is an additive mode built from the V2 planning harness. It leaves
`naive`, `data-v2.2`, `data-v2.2-v2`, and the V2 no-knowledge control unchanged.
Its own retrieval control is the sibling mode `data-v2.3-no-knowledge`; see
[data-v2.3-no-knowledge.md](data-v2.3-no-knowledge.md).
Its two goals are to remove provider-native tool-call coupling and reduce the
negative transfer observed when retrieved SC2 facts were relevant in isolation
but not executable in the live match.

## Portable invocation contract

Every remote model interaction is an ordinary text chat completion. V2.3 does
not send `tools`, `tool_choice`, function-call messages, or vendor-specific tool
schemas to MainAgent or DataSubAgent.

```text
observation + V2 planning snapshot
                |
                v
       MainAgent JSON text
          |             |
          | final       | focused knowledge request
          v             v
   replacement queue   local PortableKnowledgeRouter
                              |
                              v
                 repository query functions/data
                              |
                              v
                  bounded evidence packet
                              |
                              v
             DataSubAgent ordinary text completion
                              |
                              v
                   MainAgent final JSON text
```

An API profile only needs to return response text through the repository's
normal chat-completion adapter. The local router, not the provider, selects and
executes data functions. A malformed or failed DataSubAgent summary falls back
to a deterministic summary of the evidence packet; a tool failure is reported
as unavailable evidence and does not block a survival decision.

`LLMInvoker` records `invocation_protocol=portable_text_v1` and rejects any
attempt to pass native tools. MainAgent and DataSubAgent retain independent API
profiles and may therefore use different models or endpoints.

## Knowledge routing and data improvements

Knowledge remains optional. The harness exposes nonblocking opportunities when
one of these facts can materially change the queue:

- a weapon-layer gap requires `combat_capability` evidence;
- a sufficiently large observed enemy composition justifies `enemy_counter`;
- an established army with spare resources may justify `upgrade_path`;
- an uncertain producer or prerequisite can justify `tech_feasibility`;
- bounded cost, supply, producer, and time questions use `resource_facts`.

V2.3 adds `query_composition_response_matrix`, which aggregates typed counter
edges across all named enemy units instead of selecting the first pairwise
counter. The portable router then enriches and ranks candidates by:

- direct ability to attack the observed air or ground layer;
- composition coverage ratio;
- own-race filtering and exact canonical identity;
- current producer and prerequisite readiness;
- horizon mineral/gas affordability and arrival time;
- compatibility with the strategy's fallback composition;
- mobile-combat priority over static defense outside an emergency.

The router does not require one general-purpose unit to solve a mixed army.
It now returns separate immediately executable air-layer and ground-layer
shortlists, assembles a small verified response portfolio, and promotes one
member for each real weapon-layer gap near the front of the queue. When enemy
power is already material and our power is no more than 125% of it, the harness
may query composition counters before a weapon-layer gap appears. This avoids
the previous failure mode in which correct evidence arrived only after the
standing army had already been destroyed.

The packet explicitly carries structure/flying identity, weapon target layers,
cost, supply, production sources, requirements, feasibility, and exclusions.
Workers and candidates unable to hit the target layer are excluded. Static
defense stays available for emergencies but does not displace executable mobile
army in a normal response shortlist.

### LLM weaknesses addressed by knowledge

V2.3 does not treat retrieval itself as an improvement. It uses knowledge only
where a language model is predictably weak:

- semantic counter names are checked against real weapon target layers;
- producers, morph sources, add-ons, earlier upgrade levels, and prerequisites
  are separated into completed, horizon-reachable, and missing states;
- Zerg Larva availability is derived from completed Hatchery-family assets
  because Larva are transient and absent from the macro observation;
- resource, supply, and production-throughput arithmetic remains deterministic;
- mixed enemy armies are decomposed by attack layer instead of inviting the
  model to overgeneralize from one all-purpose unit;
- verified counter evidence is requested while armies are near parity or we
  are behind, not only after our current direct-fire coverage reaches zero;
- a retrieved candidate must improve executable coverage or feasibility before
  it can change the queue;
- normal play prefers mobile combat power, while static defense can lead only
  under an actual survival emergency;
- completed or active upgrades are excluded, and a later level is not marked
  ready without its previous level and researcher;
- over-broad ontology expansions are quality-gated. For example, a race-wide
  relation cannot make Terran infantry weapons appear to benefit Siege Tanks.
  Structured upgrade descriptions and unit production/classes recover precise
  beneficiaries when the original relation graph is incomplete.

The resulting `decision_guidance` contains immediate mobile, horizon mobile,
emergency static, missing-requirement, and required-sequence fields. Only an
actionable combat packet contributes preferences to deterministic queue
assembly, and those insertions are recorded as
`fill_verified_knowledge_response` rather than being hidden inside prose.

## Decision and audit boundary

MainAgent still owns the final macro queue. Repository evidence cannot override
the current observation, resource envelope, supply forecast, producer capacity,
or prerequisite order. The public scheduler contract remains:

```json
{
  "reason": "Concise public explanation",
  "ordered_names": ["SupplyDepot", "Barracks", "Marine"]
}
```

Schema-4 records include `knowledge_v2_3`, actual model keys, reasoning flags,
query usage, selected tools, evidence source, and `knowledge_effect`. Full V2.3
traces are stored in `kv2_3_traces/` under each match directory.

## Validation

The provider-portability smoke test used `DeepSeek-V4-flash` in non-thinking
mode on KairosJunctionLE against MediumHard macro AI. It ran the complex
Terran `yamato_rust_fleet`, Protoss `dark_templar_rush`, and Zerg `lurkers`
strategies against two opposing races each: six complete matches, 82 decisions,
8 repository queries and responses, and zero LLM, tool, trace, or decision
errors. All 99 model requests in the corresponding traces used
`portable_text_v1`.

The frozen Hard validation used a 1200-second (20:00 game-time) limit. The final
portfolio batch completed all six matchups at 1 win, 3 ties, and 2 losses,
versus 1/3/2 for the no-external-knowledge V2 harness and 0/0/6 for naive. It
raised average resource-use rate from 1160.9 to 1392.9 and APU from 0.618 to
0.632 relative to the no-external-knowledge harness, while average resource
float remained worse. All 251 model requests used `portable_text_v1`; 96 local
tool requests had matching responses. Full matchup results, pre-portfolio
attribution, recovery-state validation fix, and limitations are recorded in
[V2.3 validation report](../test/V2_3_VALIDATION_REPORT.md). Six matches are a
functional and directional check, not a statistically stable win-rate claim.

## Run

```powershell
python run_vs_ai.py `
  --decision-agent-mode data-v2.3 `
  --decision-model DeepSeek-V4-flash `
  --data-subagent-model DeepSeek-V4-flash `
  --force-strategy lurkers
```
