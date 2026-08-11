# Documentation

## Current SC2 Agent

| Document | Purpose |
|---|---|
| [SC2_BATCH_EXPERIMENT_POLICY.md](SC2_BATCH_EXPERIMENT_POLICY.md) | Canonical bundled-runtime, staggered launch, clean-result, bounded retry, and match-local cleanup policy |
| [SC2_OBSERVATION_NOT_RETURNING_ROOT_CAUSE_AND_FIX.md](SC2_OBSERVATION_NOT_RETURNING_ROOT_CAUSE_AND_FIX.md) | Final root cause, fix, and 15/15 Qwen3-32B validation for the Human-Skill observation stall |
| [MARKDOWN_DOCUMENTATION_AUDIT_20260811.md](MARKDOWN_DOCUMENTATION_AUDIT_20260811.md) | Scope and decisions from the repository-wide Markdown consistency audit |
| [system-architecture.md](system-architecture.md) | Ten-section prompt, three-race context, strategy registry, queue replacement, scheduler, automation profiles, and records |
| [test-run-workflow.md](test-run-workflow.md) | Static tests, 15-strategy model probes, SC2 sweeps, startup checks, and record audits |
| [environment-setup.md](environment-setup.md) | Python, StarCraft II, model configuration, startup controls, and first run |
| [experiment-configuration.md](experiment-configuration.md) | Versioned experiment templates, local instances, validation, tmux, resume, and manifests |
| [reasoning-profile-routing.md](reasoning-profile-routing.md) | Per-role reasoning authority, no-knowledge exception, truthful logs, and experiment acceptance |
| [data-v2.2-decision-agent.md](data-v2.2-decision-agent.md) | DataAgent V1 boundary, optional knowledge routing, and Kimi validation |
| [data-v2.2-v2-decision-agent.md](data-v2.2-v2-decision-agent.md) | DataAgent V2 resource-to-strength planning, attack-layer knowledge, and DeepSeek validation |
| [data-v2.2-v2-no-knowledge.md](data-v2.2-v2-no-knowledge.md) | V2 control: same MainAgent wording, tool-free direct-answer SubAgent, probes and history |
| [data-v2.3-decision-agent.md](data-v2.3-decision-agent.md) | Portable text-only knowledge orchestration, composition-level evidence routing, feasibility filters, and validation |
| [data-v2.3-no-knowledge.md](data-v2.3-no-knowledge.md) | V2.3 control: same MainAgent wording, tool-free direct-answer SubAgent |

## Preserved Sharpy reference

| Document | Purpose |
|---|---|
| [python-sc2-runtime.md](python-sc2-runtime.md) | Repository-bundled python-sc2 loading rules |
| [bot-inheritance.md](bot-inheritance.md) | Sharpy and bot class inheritance |
| [sharpy-overview.md](sharpy-overview.md) | Sharpy framework overview |
| [sharpy-modules-and-config.md](sharpy-modules-and-config.md) | Sharpy modules and configuration |

The original Sharpy bots, loaders, ladder scripts, diagrams, and reference
documents are intentionally retained. Only the obsolete SC2 Agent
multi-model pipeline, Supply Planner, BO-list runtime, and their dedicated
experiment documents/scripts were removed.

Historical incident timelines are stored under `docs/archive/`; they are not
normative launch instructions.
