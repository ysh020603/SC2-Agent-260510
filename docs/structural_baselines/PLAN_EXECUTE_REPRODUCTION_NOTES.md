# Plan-and-Execute Reproduction Notes

## Sources reviewed

1. **Wang et al., ACL 2023** — *Plan-and-Solve Prompting*
   - https://aclanthology.org/2023.acl-long.147/
   - Authors' code: https://github.com/AGI-Edgerunners/Plan-and-Solve-Prompting
2. **LangChain, 2023** — *Plan-and-Execute Agents*
   - https://www.langchain.com/blog/plan-and-execute-agents
3. Current repository naive path: `SC2_Agent/decision_agent.py` +
   `dummies/generic/universal_llm_bot.py` else-branch.

## Method identity for this repo

This baseline is **not** a single-prompt Plan-and-Solve string
("Let's devise a plan and solve step by step.").

It reproduces the **LangChain-style harness**:

```text
Planner (once)
  → ordered high-level steps
  → sequential Executor(step, previous results)
  → deterministic concatenate of queue fragments
```

Plan-and-Solve is used only to confirm the invariant of planning before
solving / decomposing into subtasks.

## Confirmed algorithmic invariants

| Invariant | Source | SC2 adaptation |
|---|---|---|
| Separate higher-level planning from shorter-term execution | LangChain blog | Planner vs Executor roles |
| Plan once at the start; classic initial version does not replan every step | LangChain "Future Directions" notes revisiting plans as future work | No intra-decision replan |
| Sequential execution; later steps see prior intermediate results | LangChain | Executor receives previous fragments |
| More LLM calls than a direct action agent | LangChain | 1 + N calls, N in [1, 4] |
| Planning before solving / subtask decomposition | Plan-and-Solve | Semantic `steps[].objective` |

## Explicit SC2-only adaptations (not from papers)

- Max **4** planner steps (bounded compute per macro decision).
- Executor emits canonical macro **queue fragments**, not tool calls.
- Final public queue is **deterministic concatenation** (no Finalizer LLM).
- Aggregate queue length > 20 → decision invalid (fail-closed).
- Frozen observation for the entire Planner→Executor chain.
- No knowledge tools / DataSubAgent / V2 deterministic auditor.

## Repository audit snapshot

- Branch: `SC2-Agent-knowlegde`
- Starting commit: `60f6716eedd209b4cbf938366955f53d145af693`
- Working tree at audit: only untracked
  `SC2_STRUCTURAL_HARNESS_BASELINES_IMPLEMENTATION_PLAN.md`
- Naive remains the single-call else branch in `UniversalLLMBot`.
- New package: `SC2_Agent/baseline_plan_execute/`
- CLI mode: `plan-execute`
