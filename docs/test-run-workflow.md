# SC2 Agent 测试运行流程记录

> **脚本位置提示**：本仓库的启动、批量、sweep 等测试脚本统一归档在 [`tools/`](../tools/)。新建脚本请放入 `tools/`（或 `tools/tests/`、`tools/archive/`），不要留在仓库根目录。查找已有入口时，优先在 `tools/` 搜索 `start_*.sh`、`run_*.py`、`run_*.sh`。

本文记录当前仓库推荐的单局实验与模型评估流程。所有运行产物统一写入仓库内 `game_records/`：

```text
# Windows 示例
C:\code\SC2_Agent_OLD\game_records

# Linux 示例
/data2/SC2_shy/SC2_OLD/sharpy-sc2/game_records
```

旧的一次性 launcher 已归档到 `tools/archive/`。新实验请优先使用通用模板：

```text
tools/run_experiment.py
```

## 测试脚本归档规则

测试结束后，应在汇报结果前整理本次使用或新增的脚本：

| 脚本类型 | 归档位置 | 说明 |
|---|---|---|
| 可复用的启动、批量、回归、数据检查脚本 | `tools/` | 后续实验和问题复现的正式入口 |
| 不启动 SC2 的自动化测试 | `tools/tests/` | 使用 pytest，文件名为 `test_*.py` |
| 已废弃、仅供追溯的一次性 launcher | `tools/archive/` | 不得作为新实验入口 |
| 对局产物 | `game_records/` | 日志、Replay、轨迹 JSON、LLM 调用记录，不属于脚本 |

禁止把测试脚本长期留在仓库根目录、`docs/`、`game_records/` 或 `/tmp`。完全一次性且不支撑正式测试结论的终端命令不必保存；一旦脚本需要复跑、用于得出结论或可能帮助后续排查，就必须归档到 `tools/`。

归档脚本至少满足以下要求：

- 从仓库根目录可直接执行，并使用 `Path(__file__).resolve()` 推导仓库位置，不依赖调用时的当前目录。
- 策略、地图、模型、对手、批次名、并发数和游戏时限通过命令行参数或有说明的环境变量配置。
- 默认将运行产物写入 `game_records/<batch_name>/`，不得覆盖已有实验。
- 不包含 API 密钥、Token、个人凭据或机器专用绝对路径；`SC2PATH` 和 Python 环境路径允许通过环境变量覆盖。
- 文件名表达用途，优先采用 `run_<scope>.py`、`check_<scope>.py` 或 `verify_<scope>.py`。
- 文件头说明用途、运行示例、输出目录和是否会启动 SC2/API。
- 归档后至少执行一次 `--help`、dry-run 或对应轻量测试，确认入口没有因移动而失效。

`tools/` 的目录约定和交付检查清单见 [`../tools/README.md`](../tools/README.md)。

## 测试原则

- 当前主线默认是固定策略 + Naming + DATA_TOOLS + Ordering + Supply Planner + ExecutionScheduler。
- `--decision-mode two-stage` 会将 Naming 与 Ordering 合并为 Ordered Naming；Executor Agent 仍保留。
- 旧 Mid/Down Agent 声明式执行链路已删除，不再使用 `mid_model` / `down_model`。
- Naming / Ordering 的漏项、错项、空输出是模型表现，不通过 Agent 代码自动补齐。
- 排查重点是执行机制：当 LLM 已输出合法动作后，检查 scheduler 是否正确保留、等待、下发、计数、deferred、DONE。
- `Stage4 ordering gaps` 中的 `missing` / `dropped` 是重要评估信号，应保留记录。

## 已验证环境

### Windows

- 工作目录：`C:\code\SC2_Agent_OLD`
- Conda 环境：`C:\Users\Descfly\.conda\envs\SC2_0615`
- Python：使用该环境内的 `python.exe`
- 记录目录：`game_records`

### Linux

- 工作目录：`/data2/SC2_shy/SC2_OLD/sharpy-sc2`
- Conda 环境：`/home/wyq/miniconda3/envs/SC2_0615`（Python 3.11.15）
- StarCraft II：`SC2PATH=/data2/SC2/StarCraftII/`
- 记录目录：`game_records`

## 跑之前检查

先确认本次运行会使用 Agent 自己的 `python-sc2`：

```powershell
@'
from sc2_runtime import ensure_bundled_python_sc2
print(ensure_bundled_python_sc2())
'@ | python -
```

输出必须位于当前 Agent 仓库的 `python-sc2\sc2\`。

```powershell
cd C:\code\SC2_Agent_OLD

& 'C:\Users\Descfly\.conda\envs\SC2_0615\python.exe' -m py_compile `
  run_vs_ai.py `
  bot_loader\game_starter.py `
  dummies\generic\universal_llm_bot.py `
  SC2_Agent\naming_agent.py `
  SC2_Agent\ordered_naming_agent.py `
  SC2_Agent\ordering_agent.py `
  SC2_Agent\executor_agent.py `
  SC2_Agent\execution\scheduler.py `
  SC2_Agent\execution\direct_build.py `
  SC2_Agent\data_tools\action_cost.py `
  tools\run_experiment.py
```

可选：确认没有残留对局进程。

```powershell
Get-Process python,SC2_x64 -ErrorAction SilentlyContinue |
  Select-Object Id,ProcessName,Path,StartTime
```

## 通用实验模板

模板文件：

```text
tools/run_experiment.py
```

常用命令：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:SC2_GAME_TIME_LIMIT='1200'

$py='C:\Users\Descfly\.conda\envs\SC2_0615\python.exe'
& $py tools\run_experiment.py `
  --strategy battle_cruisers `
  --batch-name battle_cruisers_eval `
  --match-prefix bc_eval `
  --enemy-race terran `
  --enemy-difficulty medium `
  --enemy-build random `
  --naming-model DeepSeek-V4-pro `
  --ordering-model DeepSeek-V4-pro `
  --executor-model DeepSeek-V4-flash `
  --decision-mode three-stage `
  --no-supply-managed `
  --game-time-limit 1200
```

后台运行并将终端输出也放入 `game_records`：

```powershell
$py='C:\Users\Descfly\.conda\envs\SC2_0615\python.exe'
$out=Join-Path (Get-Location) 'game_records\battle_cruisers_eval_stdout.log'
$err=Join-Path (Get-Location) 'game_records\battle_cruisers_eval_stderr.log'

$p=Start-Process -FilePath $py `
  -ArgumentList @(
    'tools\run_experiment.py',
    '--strategy', 'battle_cruisers',
    '--batch-name', 'battle_cruisers_eval',
    '--match-prefix', 'bc_eval',
    '--enemy-race', 'terran',
    '--enemy-difficulty', 'medium',
    '--enemy-build', 'random',
    '--naming-model', 'DeepSeek-V4-pro',
    '--ordering-model', 'DeepSeek-V4-pro',
    '--executor-model', 'DeepSeek-V4-flash',
    '--decision-mode', 'three-stage',
    '--no-supply-managed',
    '--game-time-limit', '1200'
  ) `
  -WorkingDirectory (Get-Location) `
  -RedirectStandardOutput $out `
  -RedirectStandardError $err `
  -PassThru `
  -WindowStyle Hidden

"PID=$($p.Id)"
```

## 模板参数

- `--strategy`：必填，`SKILL/<race>/` 下的策略目录名。
- `--batch-name`：写入 `game_records/<batch-name>/`。
- `--match-prefix`：短 match id 前缀，避免 Windows 路径过长。
- `--map-name`：默认 `KairosJunctionLE`。
- `--bot-race`：默认 `terran`。
- `--enemy-race`：`terran | zerg | protoss | random`。
- `--enemy-difficulty`：`easy | medium | hard | harder | veryhard` 等。
- `--enemy-build`：`air | macro | rush | timing | power | random`。
- `--naming-model`：Naming Agent 的 model key。
- `--ordering-model`：Ordering Agent 的 model key；`two-stage` 下保留但不调用。
- `--executor-model`：Executor Agent 的 model key。
- `--decision-mode`：`three-stage`（默认）或 `two-stage`。`two-stage` 使用 `--naming-model` 作为 Ordered Naming 模型。
- `--supply-managed / --no-supply-managed`：是否让 Stage5 算法托管补给站。
- `--game-time-limit`：写入 `SC2_GAME_TIME_LIMIT`，单位秒；默认 `1200`（20 游戏分钟）。
- `--run-index`：并发/批量实验时区分同组运行。

## 推荐模型组合

模型能力评估：

```text
naming_model   = DeepSeek-V4-pro
ordering_model = DeepSeek-V4-pro
executor_model = DeepSeek-V4-flash
supply_managed = false
```

稳定冒烟：

```text
naming_model   = DeepSeek-V4-flash
ordering_model = DeepSeek-V4-flash
executor_model = DeepSeek-V4-flash
supply_managed = true
```

两阶段 Kimi non-thinking 冒烟：

```powershell
$env:SC2_GAME_TIME_LIMIT='120'
$py='C:\Users\Descfly\.conda\envs\SC2_0615\python.exe'
& $py tools\run_experiment.py `
  --strategy battle_cruisers `
  --batch-name kimi_nothink_two_stage_smoke `
  --match-prefix kimi2stage `
  --enemy-race terran `
  --enemy-difficulty easy `
  --enemy-build random `
  --decision-mode two-stage `
  --naming-model Kimi-k2.5 `
  --ordering-model Kimi-k2.5 `
  --executor-model Kimi-k2.5 `
  --game-time-limit 120
```

检查点：

- `.llm_calls.json` 中应出现 `agent="ordered_naming"`。
- `.llm_calls.json` 中不应出现 `agent="ordering"`。
- `.json` 轨迹中应有 `decision_mode="two-stage"`、`ordered_naming_raw`、`ordered_names`、`ordered_name_mapping`。
- Executor Agent 仍可能在 train 多候选时出现。

## 运行中观察

查看 stderr/stdout：

```powershell
Get-Content game_records\battle_cruisers_eval_stderr.log -Tail 120
```

关键日志：

```text
Players: Bot UniversalLLMBot(Terran), Computer Medium(Terran, RandomBuild)
[strategy_steps] loaded ...
MACRO PIPELINE START (trigger=initial_step
Strategy step 1 (index=0, is_last=False) ...
Stage2 named ...
Stage3 mapped ...
Stage4 ordering gaps ...
Stage5 SUPPLY_MANAGED ...
Scheduler active queue after install ...
```

两阶段模式下关键日志会变为 `TWO-STAGE MACRO PIPELINE START`、`Ordered Naming names`、`Two-stage mapped ordered actions` 和 `Two-stage with supply`。

筛选关键行：

```powershell
Select-String -Path game_records\battle_cruisers_eval_stderr.log `
  -Pattern 'Strategy step|Stage2 named|Ordered Naming names|Stage3 mapped|Two-stage mapped|Stage4 ordering gaps|Stage5 SUPPLY_MANAGED|Two-stage with supply|Scheduler active queue|DirectBuild|Abandoned stuck|Result for player|Result:' |
  Select-Object -Last 100 |
  ForEach-Object { $_.Line }
```

## 结束后确认

```powershell
Select-String -Path game_records\battle_cruisers_eval_stderr.log `
  -Pattern 'Result for player|Result:|Victory|Defeat|Tie' |
  Select-Object -Last 20 |
  ForEach-Object { $_.Line }
```

查看产物：

```powershell
Get-ChildItem game_records\battle_cruisers_eval -Recurse |
  Select-Object Name,Length,LastWriteTime
```

完整产物应包含：

- `<match_id>.log`
- `<match_id>.json`
- `<match_id>.llm_calls.json`
- `<match_id>.SC2Replay`

## 常见坑

- `UnicodeEncodeError`：设置 `$env:PYTHONUTF8='1'` 和 `$env:PYTHONIOENCODING='utf-8'`。
- 路径过长：使用 `--match-prefix`，并保持 `--batch-name` 简短。
- `conda` 不在 PATH：直接调用 `C:\Users\Descfly\.conda\envs\SC2_0615\python.exe`。
- `Stage4 ordering gaps` 出现 `missing`：先记录为 LLM 漏项，不要在代码里补齐。
- LLM 已输出动作但 scheduler 没执行：再进入执行机制排查。
- 旧 `tools/archive/run_*.py` 仅作历史参考，新实验不要继续复制这些文件。
- 临时测试脚本完成使命后仍留在根目录、`docs/`、`game_records/` 或 `/tmp`：按“测试脚本归档规则”移动到 `tools/`，再记录最终复现命令。

## 历史回归点

`battle_cruisers` 建筑起飞问题可用通用模板复测：

```powershell
& 'C:\Users\Descfly\.conda\envs\SC2_0615\python.exe' tools\run_experiment.py `
  --strategy battle_cruisers `
  --batch-name battle_cruisers_regression `
  --match-prefix bc_reg `
  --enemy-race terran `
  --enemy-difficulty medium `
  --enemy-build random `
  --naming-model DeepSeek-V4-pro `
  --ordering-model DeepSeek-V4-pro `
  --executor-model DeepSeek-V4-flash `
  --no-supply-managed `
  --game-time-limit 1200
```

重点检查：

- Factory Tech Lab 是否正常出现。
- Starport Tech Lab 是否正常出现。
- `Stage4 ordering gaps` 是否为空。
- `Scheduler active queue after install` 中是否保留关键动作。
- 不应出现 `FACTORYFLYING`、`STARPORTFLYING`、`BARRACKSFLYING`。

## Linux 版本

### 已验证环境

- 工作目录：`/data2/SC2_shy/SC2_OLD/sharpy-sc2`
- Conda 环境：`/home/wyq/miniconda3/envs/SC2_0615`
- Python：3.11.15（`SC2_0615` 环境内）
- StarCraft II：`SC2PATH=/data2/SC2/StarCraftII/`
- 记录目录：`game_records/`（仓库内相对路径）
- 显示环境：无图形界面亦可运行（SC2 Linux 版 headless）

### 跑之前检查

```bash
source /home/wyq/miniconda3/etc/profile.d/conda.sh
conda activate SC2_0615
cd /data2/SC2_shy/SC2_OLD/sharpy-sc2

export SC2PATH=/data2/SC2/StarCraftII/

python -m py_compile \
  run_vs_ai.py \
  bot_loader/game_starter.py \
  dummies/generic/universal_llm_bot.py \
  SC2_Agent/naming_agent.py \
  SC2_Agent/ordering_agent.py \
  SC2_Agent/executor_agent.py \
  SC2_Agent/execution/scheduler.py \
  SC2_Agent/execution/direct_build.py \
  SC2_Agent/data_tools/action_cost.py \
  tools/run_experiment.py
```

导入自检：

```bash
python -c "
from sc2_runtime import ensure_bundled_python_sc2
origin = ensure_bundled_python_sc2()
import sc2, sc2pathlib, sharpy
from sharpy.plans.acts import ActBase
from SC2_Agent.execution.scheduler import ExecutionScheduler
from SC2_Agent.data_tools import actions_for_entities, plan_supply
from dummies.generic.universal_llm_bot import UniversalLLMBot
print('SC2 RUNTIME:', origin)
print('ALL IMPORTS OK')
"
```

pytest 自检（需先 `pip install "pytest<7.0.0" "pytest-asyncio==0.20.3"`）：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH="$PWD" \
  python -m pytest -q -p pytest_asyncio
```

当前 Linux 实测结果（2026-06-18）：

```text
11 passed, 26 skipped
```

可选：确认没有残留对局进程。

```bash
ps aux | grep -E 'SC2_x64|run_experiment|run_vs_ai' | grep -v grep
```

### 通用实验模板

```bash
source /home/wyq/miniconda3/etc/profile.d/conda.sh
conda activate SC2_0615
cd /data2/SC2_shy/SC2_OLD/sharpy-sc2

export SC2PATH=/data2/SC2/StarCraftII/
export SC2_GAME_TIME_LIMIT=1200

python tools/run_experiment.py \
  --strategy battle_cruisers \
  --batch-name battle_cruisers_eval \
  --match-prefix bc_eval \
  --enemy-race terran \
  --enemy-difficulty medium \
  --enemy-build random \
  --naming-model DeepSeek-V4-pro \
  --ordering-model DeepSeek-V4-pro \
  --executor-model DeepSeek-V4-flash \
  --no-supply-managed \
  --game-time-limit 1200
```

后台运行并将终端输出也放入 `game_records`：

```bash
mkdir -p game_records
nohup python tools/run_experiment.py \
  --strategy battle_cruisers \
  --batch-name battle_cruisers_eval \
  --match-prefix bc_eval \
  --enemy-race terran \
  --enemy-difficulty medium \
  --enemy-build random \
  --naming-model DeepSeek-V4-pro \
  --ordering-model DeepSeek-V4-pro \
  --executor-model DeepSeek-V4-flash \
  --no-supply-managed \
  --game-time-limit 1200 \
  > game_records/battle_cruisers_eval_stdout.log \
  2> game_records/battle_cruisers_eval_stderr.log &

echo "PID=$!"
```

### 运行中观察

```bash
tail -n 120 game_records/battle_cruisers_eval_stderr.log
```

筛选关键行：

```bash
grep -E 'Strategy step|Stage2 named|Ordered Naming names|Stage3 mapped|Two-stage mapped|Stage4 ordering gaps|Stage5 SUPPLY_MANAGED|Two-stage with supply|Scheduler active queue|DirectBuild|Abandoned stuck|Result for player|Result:' \
  game_records/battle_cruisers_eval_stderr.log | tail -n 100
```

### 结束后确认

```bash
grep -E 'Result for player|Result:|Victory|Defeat|Tie' \
  game_records/battle_cruisers_eval_stderr.log | tail -n 20

ls -la game_records/battle_cruisers_eval/*/
```

### Linux 常见坑

- `SC2PATH` 未设置：每次新开 shell 需 `export SC2PATH=/data2/SC2/StarCraftII/`，或写入 `~/.bashrc`。
- 地图找不到：确认 `KairosJunctionLE` 在 `$SC2PATH/Maps/` 下（本机已有 `KairosJunctionLE_20264.SC2Map` 等）。
- `conda` 未激活：先 `source .../conda.sh && conda activate SC2_0615`。
- pytest 启动报 `_pytest.scope`：使用 `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`（见上文）。
- 并发批量实验：可用仓库内 `tools/run_vs_ai_batch.sh` 或 `tools/start_experiments.sh`，注意机器上其他用户的 SC2 进程占用端口。

### Linux 冒烟实测（2026-06-18）

```bash
export SC2PATH=/data2/SC2/StarCraftII/
export SC2_GAME_TIME_LIMIT=120

python tools/run_experiment.py \
  --strategy battle_cruisers \
  --batch-name linux_smoke \
  --match-prefix lx_smoke \
  --enemy-race terran \
  --enemy-difficulty easy \
  --enemy-build random \
  --naming-model DeepSeek-V4-flash \
  --ordering-model DeepSeek-V4-flash \
  --executor-model DeepSeek-V4-flash \
  --supply-managed \
  --game-time-limit 120
```

实测结果：

- 对局约 35 秒完成（`SC2_GAME_TIME_LIMIT=120`，游戏内约 2 分钟 Tie）
- `Stage4 ordering gaps` 均为 `missing: [], dropped: []`
- 产物完整：`.json`、`.llm_calls.json`、`.log`、`.SC2Replay`
- 记录目录：`game_records/linux_smoke/20260618_174643_lx_smoke/`

### Linux 历史回归点

```bash
python tools/run_experiment.py \
  --strategy battle_cruisers \
  --batch-name battle_cruisers_regression \
  --match-prefix bc_reg \
  --enemy-race terran \
  --enemy-difficulty medium \
  --enemy-build random \
  --naming-model DeepSeek-V4-pro \
  --ordering-model DeepSeek-V4-pro \
  --executor-model DeepSeek-V4-flash \
  --no-supply-managed \
  --game-time-limit 1200
```

重点检查项与 Windows 相同（Factory/Starport Tech Lab、`Stage4 ordering gaps`、scheduler 队列、无 `FACTORYFLYING` 等）。

## 当前默认测试设置

- 对手种族：Terran
- 对手难度：Medium
- 对手风格：RandomBuild（`--enemy-build random`）
- Supply 托管：默认关闭
- 对局时限：20 游戏分钟（`--game-time-limit 1200` / `SC2_GAME_TIME_LIMIT=1200`）

## BO list 直接执行模式（旁路 Naming/Ordering LLM）

通过 `--bo-list <name>` 启用。Bot 会跳过 Stage2/3/4/5 流水线，把
`BO_list/<race>/<name>/BO.json` 的 action 序列按 `BO_CHUNK_SIZE`（默认 **15**）分段，首段 `replace`、后续每段 drain 后 `append` 逐步注入 `ExecutionScheduler`；
`Executor Agent` 仅在 train 多候选时会被调用；addon/morph 规则选，不调 LLM。

最小复现：

```bash
conda activate SC2_0615
export SC2PATH=/data2/SC2/StarCraftII/
python run_vs_ai.py --bo-list marine_rush --enemy-difficulty medium --batch-name bo_smoke
```

注册要求：

- BO 策略名必须出现在 `BO_list/<race>/registry.json` 的 `registered_strategies` 中；
- 该目录下必须同时存在 `BO.json` 与 `strategy_tools.py`（与 SKILL 同名文件等价的免费工具轨）。

互斥规则：`--bo-list` 与 `--force-strategy` 不能同时显式指定。`run_vs_ai.py` 内置的 `DEFAULT_FORCE_STRATEGY` / `DEFAULT_BO_LIST` 在 CLI 显式给出另一个时会被自动屏蔽。

重点检查项：

- `.log` 中应出现 `>>> BO LIST: '<name>' loaded (<N> actions)`，之后每段注入有 `[BO list] installed chunk X/Y: ...` 行，且全程**不应**出现 `>>> MACRO PIPELINE START` 行。
- `.json` 轨迹中应出现 `trigger_reason="bo_list_loaded"` 与多条 `trigger_reason="bo_list_chunk_installed"` 事件（每分段一条，含 `chunk_index` / `total_chunks` / `chunk_range`）；不应再有 `naming_raw` / `ordering_raw` 字段。
- 后续运行依赖 scheduler 的 waiter / 资源预留 / 同档超车机制，与 force-strategy 模式完全相同（见 [system-architecture.md](system-architecture.md) §4.2 / §4.3 / §5.5）。
