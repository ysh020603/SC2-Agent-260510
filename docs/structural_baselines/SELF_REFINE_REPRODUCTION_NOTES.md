# Self-Refine Reproduction Notes

## Sources reviewed

1. **Madaan et al., NeurIPS 2023** — *Self-Refine: Iterative Refinement with Self-Feedback*
   - https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html
   - Authors' code: https://github.com/madaan/self-refine
2. Author README / acronym task structure:
   - `src/acronym/run.py`, `task_init.py`, `feedback.py`, `task_iterate.py`
3. Current repository naive path: `SC2_Agent/decision_agent.py`.

## Method identity for this repo

```text
Init → Feedback → (optional) Refine → Feedback ... → stop
```

Author tasks use three prompt families:

1. `Init` — initial generation
2. `Feedback` — critique of the current candidate
3. `Iterate` / Refine — produce a full improved output from feedback

Generator, critic, and refiner may be the **same LLM**. No RL / fine-tuning.
Feedback is an explicit intermediate artifact. Refinement is iterative.

## Confirmed algorithmic invariants

| Invariant | SC2 adaptation |
|---|---|
| Init produces a full candidate | Same public `{reason, ordered_names}` as naive |
| Feedback is actionable, not a replacement queue | `{needs_refinement, summary, issues[]}` |
| Refine emits a **full** replacement output, not a patch | Full `{reason, ordered_names}` |
| Stop when critic satisfied or max attempts | `MAX_REFINE_ROUNDS = 2` |
| Same model for all roles | `decision_model_key` only |

## Explicitly excluded (would become Reflexion / memory agents)

- Cross-decision reflection memory
- Cross-game episodic memory
- Knowledge retrieval / DataSubAgent
- Hidden ground-truth enemy state for the critic
- V2 deterministic audit results fed into Feedback

## Explicit SC2-only adaptations

- Default `MAX_REFINE_ROUNDS = 2` (bounded compute).
- Call accounting: Init=1; each refine round = Feedback+Refine; no extra
  post-limit Feedback after the max refine.
- Malformed Feedback / Refine → accept last valid candidate (fail soft after Init).
- Malformed Init → whole decision invalid (old queue kept).
- Frozen observation across all rounds of one decision.

## Repository audit snapshot

- Branch: `SC2-Agent-knowlegde`
- Starting commit: `60f6716eedd209b4cbf938366955f53d145af693`
- Working tree at audit: only untracked
  `SC2_STRUCTURAL_HARNESS_BASELINES_IMPLEMENTATION_PLAN.md`
- New package: `SC2_Agent/baseline_self_refine/`
- CLI mode: `self-refine`
