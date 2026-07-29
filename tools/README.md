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
- `run_strategy_sweep_tmux.sh`: Linux wrapper for the sweep;
- `run_vs_ai_batch.sh`: simple repeated-match runner;
- `tests/`: tests that do not need a live match unless their name says runtime.

General Sharpy/ladder scripts outside this focused list are retained. They are
not obsolete merely because they do not launch `UniversalLLMBot`.

Never place API credentials in these scripts. Model endpoints belong in the
ignored `API_config/config.json`.
