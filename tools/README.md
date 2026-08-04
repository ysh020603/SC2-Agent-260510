# Tools

The supported launchers all use the same runtime contract:

- one `--decision-model`;
- one `--decision-interval` in in-game seconds;
- one fixed summary strategy selected by `--force-strategy`;
- no Naming, Ordering, Executor, Supply Planner, or BO-list modes.

Entrypoints:

- `run_experiment.py`: one explicit match;
- `run_kimi_nothink_bc.py`: one Kimi non-thinking battle-cruiser smoke match;
- `run_kimi_nothink_strategy_sweep.py`: configurable concurrent sweep;
- `run_experiment_config.py`: validate and launch versioned multi-sweep JSON suites;
- `run_experiment_config_tmux.sh`: Linux tmux wrapper for a JSON suite;
- `run_strategy_sweep_tmux.sh`: legacy environment-variable wrapper for one sweep;
- `run_vs_ai_batch.sh`: simple repeated-match runner;
- `tests/`: tests that do not need a live match unless their name says runtime.

General Sharpy/ladder scripts outside this focused list are retained. They are
not obsolete merely because they do not launch `UniversalLLMBot`.

Never place API credentials in these scripts. Model endpoints belong in the
ignored `API_config/config.json`.

For repeatable comparisons, copy a tracked template from
`experiment_configs/templates/` to the ignored `experiment_configs/local/`
directory. See `docs/experiment-configuration.md` for validation, launch,
resume, concurrency, and manifest behavior.
