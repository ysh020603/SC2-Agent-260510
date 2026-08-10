# Experiment configuration

Large comparisons are described by versioned JSON templates instead of copied
shell scripts or long command lines. The existing sweep runner remains the only
implementation of match expansion, retry, resume, and per-match concurrency;
the configuration runner validates a suite and translates it into calls to that
runner.

## Files and ownership

| Path | Git policy | Purpose |
|---|---|---|
| `experiment_configs/schema.json` | tracked | editor schema and field reference |
| `experiment_configs/templates/*.example.json` | tracked | reviewable scientific templates |
| `experiment_configs/local/*.json` | ignored | machine-specific run instances and batch names |
| `tools/experiment_config.py` | tracked | strict loading, merge, validation, and CLI translation |
| `tools/run_experiment_config.py` | tracked | validation, foreground/tmux orchestration, and manifests |

API URLs and credentials do not belong in an experiment file. Model keys refer
to complete profiles in the ignored `API_config/config.json`.
The profile's `is_reasoning` value, rather than an experiment name containing
`think`, determines the actual mode. See
[reasoning-profile-routing.md](reasoning-profile-routing.md).

## Prepare a run

Copy a template, then change its suite name, batch names, model keys, execution
parallelism, and host environment as needed:

```bash
cp experiment_configs/templates/matrix450-three-mode.example.json \
  experiment_configs/local/matrix450-20260805.json
```

On Windows, remove the template's Linux `SC2PATH` value or replace it with the
local installation. The local file is ignored by Git. If a new comparison
shape should become standard, add a sanitized `.example.json` template instead
of committing a machine-specific instance.

Every enabled experiment inherits `defaults` and may override any sweep field.
After merging, all sweep fields are required. This prevents a future change to
Python CLI defaults from silently changing an old experiment.

## Validate and inspect

```powershell
python tools\run_experiment_config.py `
  --config experiment_configs\local\matrix450-20260805.json `
  --validate

python tools\run_experiment_config.py `
  --config experiment_configs\local\matrix450-20260805.json `
  --dry-run
```

Validation rejects unknown or misspelled fields, unsupported modes/races/builds
and difficulties, invalid or disabled strategies, empty matrices, duplicate
experiment names, duplicate enabled batch names, and paths that escape the
repository. It also expands the matrix and reports the exact job count. The
tracked 450 templates must report 450 jobs for every experiment group.

Supported `decision_agent_mode` values include `naive`, `data-v2.2`,
`data-v2.2-v2`, `data-v2.2-v2-no-knowledge`, `data-v2.3`, and
`data-v2.3-no-knowledge`, plus the knowledge-free structural baselines
`plan-execute`, `self-refine`, `suntzu`, `hima`, and `cos`. Structural roles
all use `decision_model`; `data_subagent_model` remains accepted by the shared
experiment schema but is not used by these five modes. V2.3 requires no
special API fields beyond normal response text; the model and subagent profiles
remain independently configurable.

`--dry-run` prints the exact commands without starting SC2. Use
`--print-commands` when shell-ready command text is the only desired output.

## Launch and resume

Launch using the config's `execution.backend`:

```bash
python tools/run_experiment_config.py \
  --config experiment_configs/local/matrix450-20260805.json
```

The tmux convenience wrapper explicitly selects the tmux backend:

```bash
bash tools/run_experiment_config_tmux.sh \
  --config experiment_configs/local/matrix450-20260805.json
```

The tmux backend creates one outer suite session. The suite process then starts
experiment groups sequentially or concurrently according to
`parallel_experiments` and `max_parallel_experiments`. A pre-existing session
is never killed unless the local config explicitly sets
`replace_existing_tmux_session` to `true`.

Run or resume only selected groups without editing the config:

```bash
python tools/run_experiment_config.py \
  --config experiment_configs/local/matrix450-20260805.json \
  --experiment v1_nothink \
  --experiment v2_think \
  --start-index 120
```

`--start-index` is a temporary override and is recorded as a resolved value.
The underlying sweep also skips any index that already has a parseable result,
so restarting the same batch is safe. Do not change the matrix order while
resuming an existing batch because run indexes identify matrix positions.

## Execution fields

| Field | Meaning |
|---|---|
| `backend` | `foreground` or one outer `tmux` session |
| `parallel_experiments` | whether multiple sweep processes may overlap |
| `max_parallel_experiments` | maximum simultaneous sweep processes |
| `experiment_stagger_seconds` | gap between group submissions |
| `log_root` | repository-relative directory for orchestration logs |
| `tmux_session_prefix` | safe prefix for the suite session |
| `replace_existing_tmux_session` | explicit permission to replace that exact session |
| `environment` | non-secret environment values inherited by sweeps |

Parallelism is two-level: total possible SC2 clients are approximately
`max_parallel_experiments × concurrency`. Select both values according to host
CPU, memory, graphics capacity, and provider rate limits.

## Reproducibility record

Every foreground execution writes an ignored JSON manifest under
`game_records/_experiment_manifests/`. It records:

- source-config SHA-256 and absolute source path;
- current Git commit, host, platform, Python version, and timestamps;
- resolved values and exact command for every selected group;
- expected job count, batch name, status, and exit code.

Each experiment also receives an orchestration log below `execution.log_root`.
Per-match logs and results retain their existing locations and formats. The
manifest does not copy API configuration or credentials.

## Canonical 450-game matrix

The templates reproduce the earlier full baseline layout:

```text
5 enabled strategies per race
× 3 bot races
× 1 map (KairosJunctionLE)
× 3 enemy races
× 5 difficulties (Easy, Medium, MediumHard, Hard, Harder)
× 2 repeats
= 450 matches per experiment group
```

`matrix450-three-mode.example.json` compares naive, DataAgent V1, and DataAgent
V2. `matrix450-qwen-four-group.example.json` captures the four-group
naive/V2 × thinking/non-thinking Qwen ablation that previously required a
one-off shell script.

Before counting a thinking batch, audit its knowledge trace and require the
configured key, resolved key, `profile_reasoning_mode`, `reasoning_requested`,
and `is_reasoning` to agree. A batch or experiment name is not sufficient
evidence.
