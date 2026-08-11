# Environment setup

## Python

Python 3.11 is the established runtime. A minimal environment needs the SC2
protocol/runtime packages, OpenAI client, Sharpy dependencies, and pytest:

```bash
pip install s2clientprotocol mpyq portpicker openai requests aiohttp \
  numpy scipy scikit-learn opencv-python-headless more-itertools six \
  "protobuf==3.20.3" loguru pytest pytest-asyncio
```

The repository loads its bundled `python-sc2/` snapshot through
`sc2_runtime.py`; do not rely on a different site-packages `sc2`.
The existing Sharpy `bot_loader/` remains the common startup layer for both
the retained demo bots and `UniversalLLMBot`.

The `data-v2.2` decision runtime and its complete SC2 dataset are vendored
under `SC2_Agent/knowledge_v2_2/`. A checkout of the sibling
`SC2_DATA_Agent` repository is not required at runtime.
The additive planning mode `data-v2.2-v2` has its own copied runtime, prompts,
and dataset under `SC2_Agent/knowledge_v2_2_v2/`; V1 remains independent.
The additive `data-v2.3` runtime is under `SC2_Agent/knowledge_v2_3/`. It owns
its prompts and routing code but reuses the immutable repository-local V2 data
release; it never imports the sibling `SC2_DATA_Agent` checkout.

## StarCraft II

Set `SC2PATH` to the StarCraft II root and make sure the requested map exists.

Windows PowerShell example:

```powershell
$env:SC2PATH='C:\Program Files (x86)\StarCraft II'
Get-ChildItem "$env:SC2PATH\Maps" -Recurse -Filter '*Kairos*'
```

Linux example:

```bash
export SC2PATH=/data2/SC2/StarCraftII/
find "$SC2PATH/Maps" -iname '*Kairos*'
```

On Windows, do not inject a Linux `SC2PATH` into child processes. The sweep
runner leaves discovery to the registry/default installation. Concurrent batch
launches use a two-second gap by default to avoid initializing several clients
in the same instant.

正式批量实验还必须自然等待子进程、只统计可解析且无 timeout/watchdog 污染的
引擎结果、单独有限重试失败条件，并永久禁止全局 `wineserver -k`。不要从本页
零散示例推导运行策略；以
[`SC2_BATCH_EXPERIMENT_POLICY.md`](SC2_BATCH_EXPERIMENT_POLICY.md) 为准。

SC2 websocket startup waits up to 180 seconds by default. Override it for a
known slow host with either the sweep option or the child environment:

```powershell
python tools\run_kimi_nothink_strategy_sweep.py `
  --startup-timeout 240 `
  --launch-stagger-seconds 3 `
  --dry-run

$env:SC2_STARTUP_TIMEOUT='240'
```

If SC2 exits before its websocket is available, the runtime reports the exit
code immediately. If the process remains alive but never publishes the
endpoint, it reports a bounded timeout that the sweep runner can retry.

## LLM configuration

Create `API_config/config.json` from the repository's expected config shape.
The file is ignored by Git. The supported runtime accepts one model key:

```json
{
  "llm_agents_pool": {
    "Kimi-k2.5": {
      "api_url": "http://host/v1",
      "api_key": "replace-locally",
      "model_name": "kimi-k2.5",
      "temperature": 1,
      "top_p": null,
      "max_tokens": null,
      "is_reasoning": false,
      "reasoning_extract_mode": "none",
      "non_reasoning_temperature": 0.6,
      "non_reasoning_extra_body": {
        "thinking": {"type": "disabled"},
        "chat_template_kwargs": {"thinking": false}
      }
    }
  }
}
```

Never commit or echo the real credential.

MainAgent and DataSubAgent accept independent model keys. Each key selects its
own complete entry in `llm_agents_pool`, so the roles may use different
`api_url`, `api_key`, and `model_name` values. The defaults are both
`Kimi-k2.5` non-thinking. `data-v2.2` may make several calls when MainAgent
chooses to query knowledge. A package-local cross-process rate limiter defaults
Kimi to 50 calls per rolling minute. If the configured provider quota is
different, set a safe value from 1 through the provider maximum:

```powershell
$env:SC2_KIMI_RPM='50'
```

The selected profile's `is_reasoning` value controls every normal call for that
role; the knowledge launcher has no separate reasoning switch. A `_think`
suffix is only a naming convention. Validate configured/resolved keys and the
reasoning fields described in
[reasoning-profile-routing.md](reasoning-profile-routing.md).

## Verify without a match

```powershell
python run_vs_ai.py --help
python run_custom.py --help
python tools\run_experiment.py --help
python tools\run_kimi_nothink_strategy_sweep.py --dry-run
python tools\run_experiment_config.py --config experiment_configs\templates\matrix450-three-mode.example.json --validate
python API_Tools\probe_reasoning_extraction.py --model-key Kimi-k2.5 --max-tokens 256
python -m pytest tools\tests -q
```

## First match

```powershell
$env:SC2_GAME_TIME_LIMIT='240'
python tools\run_experiment.py `
  --decision-agent-mode data-v2.2 `
  --strategy marine_rush `
  --bot-race terran `
  --decision-model Kimi-k2.5 `
  --data-subagent-model Kimi-k2.5 `
  --decision-interval 60 `
  --enemy-race terran `
  --enemy-difficulty medium `
  --batch-name first_data_v2_2_test
```

Use `--decision-agent-mode naive` to run the preserved baseline. See
[data-v2.2-decision-agent.md](data-v2.2-decision-agent.md) for the mode boundary
and [data-v2.2-v2-decision-agent.md](data-v2.2-v2-decision-agent.md) for the
planning and combat-capability mode,
and [test-run-workflow.md](test-run-workflow.md) for record validation.
Use [experiment-configuration.md](experiment-configuration.md) for repeatable
multi-group comparisons. Tracked templates contain no credentials; copy them
to ignored `experiment_configs/local/` before assigning real batch names and
machine-specific execution settings.
