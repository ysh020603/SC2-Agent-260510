# SC2 Agent OLD

这是一个基于 Sharpy / python-sc2 的《星际争霸 II》LLM Bot 实验仓库。当前代码的主线已经从旧版 `Top/Mid/Down` 声明式三层 Agent，迁移为：

```text
固定策略 Top_agent_<enemy_race>.md
  -> Naming Agent
  -> DATA_TOOLS 映射
  -> Ordering Agent
  -> Supply Planner
  -> ExecutionScheduler
  -> Sharpy / SC2
```

也可以用 `--decision-mode two-stage` 将 Naming 与 Ordering 合并为 `Ordered Naming Agent`：

```text
固定策略 Top_agent_<enemy_race>.md
  -> Ordered Naming Agent
  -> DATA_TOOLS 映射
  -> Supply Planner
  -> ExecutionScheduler
  -> Sharpy / SC2
```

一句话说：玩家先固定一个人族策略目录，系统读取该策略的阶段说明，把每个阶段拆成标准单位、建筑、科技动作，再用命令式调度器逐帧执行。默认仍是原 `three-stage` 模式。

当前主线只适配 Terran。Protoss / Zerg 的 Sharpy dummy bot 仍在仓库里，但 LLM 增量流水线和 `SKILL` 策略库目前按人族维护。

## 当前状态

- 主入口：`run_vs_ai.py`
- 通用 LLM Bot：`dummies/generic/universal_llm_bot.py`
- 策略目录：`SKILL/terran/<strategy>/`
- 策略文件：`SKILL/terran/<strategy>/Top_agent_<enemy_race>.md`
- 策略工具轨：`SKILL/terran/<strategy>/strategy_tools.py`
- 模型配置：`API_config/config.json`
- 对局记录：`game_records/`

重要变化：

- `UniversalLLMBot` 现在必须指定固定策略，`--force-strategy none` 会报错。
- 旧的 t=0 交互式策略选择、Mid/Down Agent 声明式执行路径已删除。
- 当前关键 LLM 调用点是 `--naming-model`、`--ordering-model`、`--executor-model`；`--decision-mode` 控制 Naming/Ordering 是否合并。

## 仓库结构

```text
SC2_Agent/
  naming_agent.py              # Stage 2: 策略 step + obs -> 标准实体名和数量
  ordered_naming_agent.py      # two-stage: 策略 step + obs -> 有序标准实体名展开列表
  ordering_agent.py            # Stage 4: 对标准 action 排序
  executor_agent.py            # 为 train 选择执行单位（addon/morph 规则选）
  data_tools/                  # 内置 SC2 数据库、标准名、成本、前置、冲突、补给规划
  execution/
    command.py                 # PlannedAction 状态对象
    direct_build.py            # Terran 普通建筑直接建造执行器
    executor_select.py         # 候选执行单位筛选
    mapping.py                 # 标准 action 与 SC2 / Sharpy 枚举映射
    scheduler.py               # ExecutionScheduler 核心调度器

dummies/generic/
  universal_llm_bot.py         # 编排策略读取、三/两阶段决策流水线、调度器和记录落盘

SKILL/terran/
  registry.json                # 人族策略白名单/索引（force-strategy 模式）
  marine_rush/
  battle_cruisers/
  banshees/
  bio/
  cyclones/
  one_base_turtle/
  rusty/
  safe_tvt_raven/
  terran_silver_bio/
  two_base_tanks/

BO_list/terran/                # BO list 直接执行模式（bo-list 模式）
  registry.json                # 已注册 BO list 策略名单
  marine_rush/
    BO.json                    # 标准 action 名顺序列表（分段喂入 ExecutionScheduler）
    strategy_tools.py          # 不耗资源的后台战术（与 SKILL 同名文件等价）

API_config/
  config.example.json          # OpenAI 兼容模型配置模板
  config.json                  # 本地实际模型配置，不要提交真实 key

bot_loader/                    # Bot 注册、对局启动、内置 AI 参数解析
sharpy/                        # Sharpy 框架主体
python-sc2/                    # Agent 自己版本化的固定 python-sc2 运行时
sc2_runtime.py                # 本地运行时加载、来源校验和兼容性检查
docs/                          # 系统说明、环境配置、测试记录和经验总结
```

## 核心流程

### 1. 固定策略

运行时通过 `--force-strategy <name>` 指定策略目录，例如：

```bash
python run_vs_ai.py --force-strategy marine_rush
```

策略名对应：

```text
SKILL/terran/marine_rush/
  Top_agent_terran.md
  Top_agent_protoss.md
  Top_agent_zerg.md
  strategy_tools.py
```

策略文件按对手种族选择：`--enemy-race zerg` 会读取 `Top_agent_zerg.md`，`--enemy-race protoss` 会读取 `Top_agent_protoss.md`，`--enemy-race terran` 会读取 `Top_agent_terran.md`。文件中的 `# Details` 会被解析为若干 `[Step N]`，`# Summary` 同时作为宏观指导注入后续 LLM prompt。每次宏观流水线触发时，Bot 取当前 step 原文作为本轮宏观目标；到达最后一个 step 后会持续复用最后 step，直到对局结束。

### 2. 五阶段宏观流水线

触发入口在 `UniversalLLMBot.pre_step_execute()`。首次进入、动作序列执行完、或队列只剩 deferred 动作时，会 append 下一阶段动作。

五阶段如下：

| 阶段 | 作用 |
|---|---|
| Strategy Step Source | 按对手种族读取当前策略 step 文本；所有 step 走完后复用最后 step |
| Naming Agent | 将自然语言目标转成 Terran 标准实体名和数量 |
| DATA_TOOLS | 将实体名映射成标准 action key，并提供成本、前置、冲突信息 |
| Ordering Agent | 在前置、冲突、成本提示下对 action 排序 |
| Supply Planner | 默认托管补给站插入，避免供给卡死 |

Ordering 阶段不会用代码补齐 LLM 漏掉的动作。漏项和非法项会写入轨迹 JSON，用来保留模型评估信号。

### 3. 两阶段 Ordered Naming 模式

`--decision-mode two-stage` 会把 Naming 与 Ordering 合并为一次 LLM 调用：

```bash
python run_vs_ai.py --force-strategy marine_rush --decision-mode two-stage
```

该模式下 `Ordered Naming Agent` 直接输出有序的 canonical Unit/Upgrade 名称展开列表，例如：

```json
{"ordered_names":["SupplyDepot","Barracks","BarracksTechLab","Marine","Marine","Marine"]}
```

注意事项：

- `--naming-model` 作为 `Ordered Naming Agent` 的模型 key 使用。
- `--ordering-model` 保留参数但不会调用，方便旧实验脚本兼容。
- `--executor-model` 不变，仍由 `ExecutionScheduler` 在 train 多候选时调用。
- 下游 DATA_TOOLS 映射、Supply Planner、ExecutionScheduler 和 Executor Agent 都复用原实现。

### 4. 命令式执行调度

`ExecutionScheduler` 每帧执行 action 队列，核心机制包括：

- `PENDING / WAITING / RUNNING / DONE / ABANDONED` 状态机
- 独立 waiter 槽，等待资源、科技、人口或执行单位
- P0 / P1 / P2 优先级扫描：补 supply 的动作优先，不耗 supply 的动作次之，训练单位最后
- waiter 资源预留和同档超车
- 科技前置检测和缺失前置自动插入
- Terran 普通建筑的 DirectBuild 独立 reservation / target
- train 可调用 Executor Agent 选择执行单位（addon / morph 由规则直选）
- waiting 超时和 running 卡死放弃，避免宏观队列永久堵塞

### 5. 策略工具轨

`create_plan()` 并行运行两条轨：

- `ExecutionScheduler`：执行五阶段流水线产出的资源动作。
- 当前策略自己的 `strategy_tools.py`：只放不消耗 minerals / gas / supply 的辅助战术工具。

没有全局后台战术 fallback。某个策略缺少侦察、攻击或防守工具时，需要在该策略自己的 `strategy_tools.py` 中补。

### 6. BO list 直接执行模式（旁路 LLM 流水线）

除上面的「固定策略 + 五阶段流水线」之外，`UniversalLLMBot` 还支持一种 **BO 直接执行模式**：完全跳过 Naming / Ordering / Supply Planner，把 `BO.json` 中的标准 action 序列按 `BO_CHUNK_SIZE`（默认 **15**）分段注入 `ExecutionScheduler`（首段 `replace`，当前段 drain 后 `append` 下一段）。

启用方式（与 `--force-strategy` 互斥）：

```bash
python run_vs_ai.py --bo-list marine_rush
```

策略目录结构（注册才能用，与 SKILL 同模式）：

```text
BO_list/terran/registry.json          # "registered_strategies": ["marine_rush", ...]
BO_list/terran/<name>/
  BO.json                             # JSON 数组，元素是标准 action 名（如 TERRANBUILD_SUPPLYDEPOT、BARRACKSTRAIN_MARINE）
  strategy_tools.py                   # 不耗资源的后台战术，与 SKILL 同名文件等价
```

行为约定：

- **分段注入**：`on_start` 加载整条 `BO.json` 到内存；首帧取前 15 条 `replace` 进 scheduler；当前段 drain（`is_drained_for_macro()`）且距上次装段 ≥ `MACRO_MIN_RETRIGGER`（5s）时，取下一段 `append`。续作语义与 force-strategy 的 step append 一致。
- **跳过 LLM**：Stage 2/4/5 的 Naming / Ordering / Supply Planner 不再被调用；`--naming-model` / `--ordering-model` 在该模式下变为可选（不报错、不调用）。
- **保留 Executor LLM**：`--executor-model` 仍然生效。`ExecutionScheduler` 在 train 这类存在多个候选生产单位时，依然会通过 `executor_agent` 让 LLM 选择具体执行单位。
- **保留 Scheduler 全部能力**：独立 waiter 槽（跨分段自然延续）、矿/气/人口预留、同档超车、跨档隔离、deferred 同名 build、`wait_abandon` / `running_abandon` 超时这些机制全部继续生效。BO 模式只是把 action 列表的来源从 LLM 改成了 BO.json，下游执行机制一字不改。
- **不做循环 / 不回退**：BO 所有分段装完并执行完之后，scheduler 队列保持空闲；后台 `strategy_tools.py` 继续运行；不会回退到 LLM 流水线，也不会循环重放 BO。
- **注册校验**：未在 `BO_list/<race>/registry.json` 的 `registered_strategies` 中列出的名字会直接报错。
- **互斥**：`--force-strategy` 与 `--bo-list` 两选一，同时显式指定会报错。

详细的资源预留 / 超车语义参见 [docs/system-architecture.md](docs/system-architecture.md) §4.2 / §4.3。

## 环境配置

推荐环境：

- Python 3.11
- conda 环境名：`SC2_0615`
- 本地安装 StarCraft II，并设置 `SC2PATH`
- 仓库必须包含完整的 `python-sc2/`；运行时不使用 conda/site-packages 中的 `sc2`
- Windows 下建议设置 `PYTHONUTF8=1`

详细步骤请看：

- [docs/environment-setup.md](docs/environment-setup.md)
- [docs/python-sc2-runtime.md](docs/python-sc2-runtime.md)
- [docs/system-architecture.md](docs/system-architecture.md)

最小安装示例：

```bash
conda create -n SC2_0615 python=3.11 pip -y
conda activate SC2_0615

pip install \
  "s2clientprotocol" \
  "mpyq" "portpicker" \
  "openai" "requests" "aiohttp" \
  "numpy" "scipy" "scikit-learn" \
  "opencv-python-headless" \
  "more-itertools" "six" \
  "protobuf==3.20.3" \
  "loguru"

pip install "pytest<7.0.0" "pytest-asyncio==0.20.3"
```

Windows PowerShell 常用环境变量：

```powershell
$env:SC2PATH='C:\Program Files (x86)\StarCraft II'
$env:PYTHONUTF8='1'
```

Linux 示例：

```bash
export SC2PATH=/data2/SC2/StarCraftII/
```

验证 Agent 确实加载仓库内依赖：

```bash
python -c "from sc2_runtime import ensure_bundled_python_sc2; print(ensure_bundled_python_sc2())"
```

输出路径必须位于当前仓库的 `python-sc2/sc2/`。

## LLM 配置

复制或参考 `API_config/config.example.json`，编辑 `API_config/config.json`：

```json
{
  "llm_agents_pool": {
    "DeepSeek-V4-flash": {
      "api_url": "https://api.example.com/v1",
      "api_key": "YOUR_SECRET_API_KEY",
      "model_name": "vendor-model-name",
      "temperature": 0.7,
      "top_p": null,
      "max_tokens": null,
      "is_reasoning": false,
      "reasoning_extract_mode": "none"
    }
  }
}
```

`model_key` 必须和运行参数一致。例如默认配置会使用：

- `DeepSeek-V4-flash`

可按阶段覆盖：

```bash
python run_vs_ai.py \
  --force-strategy marine_rush \
  --naming-model DeepSeek-V4-flash \
  --ordering-model DeepSeek-V4-flash \
  --executor-model DeepSeek-V4-flash
```

两阶段模式示例（`--ordering-model` 可保留但不会调用）：

```bash
python run_vs_ai.py \
  --force-strategy marine_rush \
  --decision-mode two-stage \
  --naming-model Kimi-k2.5 \
  --executor-model Kimi-k2.5
```

注意：`API_config/config.json` 可能包含真实 API key，请不要提交或公开。

reasoning 模型可以用单独的 `*_think` model_key 标注，例如
`DeepSeek-V4-flash_think`、`Kimi-k2.5_think`、`Qwen3-8b_think`。配置里的
`reasoning_extract_mode` 描述响应拆分形态，不和具体模型耦合；可选值记录在
`API_Tools/reasoning_extractors.md`。如需实测某个 API 的返回形态，可运行：

```bash
python API_Tools/probe_reasoning_extraction.py --model-key Qwen3-8b_think
```

## 运行

### 单局对战

最简单方式是先编辑 `run_vs_ai.py` 顶部的 `DEFAULT_*` 常量，然后运行：

```bash
python run_vs_ai.py
```

当前默认值包括：

- 我方：`universal_llm.terran`
- 地图：`KairosJunctionLE`
- 对手：内置 AI `terran.harder.macro`
- 固定策略：`marine_rush`

也可以用 CLI 覆盖：

```bash
python run_vs_ai.py \
  --bot-race terran \
  --enemy-race terran \
  --enemy-difficulty medium \
  --enemy-build random \
  --force-strategy battle_cruisers \
  --decision-mode three-stage \
  --batch-name demo
```

短时冒烟测试可限制游戏时长：

```bash
SC2_GAME_TIME_LIMIT=240 python run_vs_ai.py \
  --enemy-difficulty medium \
  --enemy-build random \
  --force-strategy marine_rush \
  --batch-name smoke
```

Windows 如果路径过长，推荐用 `run_custom.py` 指定短记录目录：

```powershell
$env:SC2_GAME_TIME_LIMIT='60'
New-Item -ItemType Directory -Force -Path .\game_records\smoke | Out-Null

python run_custom.py `
  -m KairosJunctionLE `
  -p1 universal_llm.terran `
  -p2 ai.terran.easy.macro `
  --record-dir .\game_records\smoke `
  --match-id smoke `
  --force-strategy marine_rush
```

### 批量对战

```bash
bash tools/start_experiments.sh
```

或直接调用底层脚本：

```bash
bash tools/run_vs_ai_batch.sh <总局数> <并发数> [fg|tmux]
```

批量脚本常用环境变量：

```bash
export MY_BOT_NAME="universal_llm"
export BOT_RACE="terran"
export ENEMY_RACE="zerg"
export ENEMY_DIFFICULTY="harder"
export ENEMY_BUILD="air"
export FORCE_STRATEGY="marine_rush"
export NAMING_MODEL="DeepSeek-V4-flash"
export ORDERING_MODEL="DeepSeek-V4-flash"
export EXECUTOR_MODEL="DeepSeek-V4-flash"
export DECISION_MODE="three-stage"
```

### 测试与运行脚本归档

测试过程中如果新建了 Python 或 Shell/PowerShell 启动脚本，测试结束后不要把脚本留在仓库根目录、`docs/`、`game_records/` 或系统临时目录。按用途整理到仓库内：

- 可复用的单局、批量、回归和结果检查脚本放入 `tools/`。
- 不启动 SC2 的 pytest 测试放入 `tools/tests/`，文件名使用 `test_*.py`。
- 已被通用脚本替代、仅保留历史参考的一次性 launcher 放入 `tools/archive/`，新测试不得继续调用。
- 对局日志、Replay、轨迹 JSON 和模型调用记录仍写入 `game_records/`，不要放进 `tools/`。

归档到 `tools/` 的脚本应从仓库根目录可直接运行，使用 `Path(__file__)` 推导仓库路径，并将地图、策略、模型、对手、并发数、批次名和时限做成参数。不得写入 API 密钥、个人凭据或只在某台机器存在的硬编码绝对路径。详细规范见 [`tools/README.md`](tools/README.md) 和 [`docs/test-run-workflow.md`](docs/test-run-workflow.md)。

## 对局产物

默认写入：

```text
game_records/<batch_name>/<match_id>/
```

常见文件：

| 文件 | 内容 |
|---|---|
| `<match_id>.log` | Sharpy 与 UniversalLLMBot 运行日志 |
| `<match_id>.SC2Replay` | SC2 录像 |
| `<match_id>.json` | 宏观流水线交互记录和结构化观测 |
| `<match_id>.llm_calls.json` | 每一次 LLM 调用的 prompt、正式 output、reasoning、raw content 与提取来源 |

轨迹 JSON 会记录：

- 固定策略名和策略说明
- 决策模式：`three-stage` 或 `two-stage`
- 每次触发原因：`initial_step`、`sequence_drained`、`executable_drained`
- 当前 strategy step
- `three-stage`：Naming 原始输出和解析后的实体
- `two-stage`：Ordered Naming 原始输出、有序实体名、实体到 action 的顺序映射
- DATA_TOOLS 映射结果
- `three-stage`：Ordering 原始输出、合法排序、漏项和丢弃项
- Supply Planner 插入的补给动作
- 注入 scheduler 的 action 序列
- 决策时英文 obs 和结构化快照

## 测试

安装测试依赖后运行：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH="$PWD" \
  python -m pytest tools/tests -q -p pytest_asyncio
```

Windows PowerShell：

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
$env:PYTHONPATH=(Resolve-Path .).Path
python -m pytest tools/tests -q -p pytest_asyncio
```

当前仓库里的轻量测试还会检查 `sc2` 的实际导入来源和 Raven 升级映射。完整游戏验证仍需要本地 SC2 客户端、地图和可用 LLM API。

如果为了复现问题临时编写了测试 launcher 或日志检查脚本，在提交测试结论前必须按上面的“测试与运行脚本归档”规则整理到 `tools/`；只有完全一次性、无需复现的终端命令可以不保存成文件。

## 常用策略名

当前 `SKILL/terran/registry.json` 中登记的策略：

- `marine_rush`
- `battle_cruisers`
- `banshees`
- `bio`
- `cyclones`
- `one_base_turtle`
- `rusty`
- `safe_tvt_raven`
- `terran_silver_bio`
- `two_base_tanks`

## 相关文档

| 文档 | 内容 |
|---|---|
| [docs/README.md](docs/README.md) | 文档阅读索引，每个 md 的用途摘要 |
| [docs/system-architecture.md](docs/system-architecture.md) | 新版 LLM 增量驱动和命令式执行系统总览 |
| [docs/environment-setup.md](docs/environment-setup.md) | Linux / Windows 环境安装、SC2PATH、冒烟测试 |
| [docs/python-sc2-runtime.md](docs/python-sc2-runtime.md) | Agent 本地 python-sc2 的加载、校验、自检与更新规则 |
| [docs/test-run-workflow.md](docs/test-run-workflow.md) | 测试和运行记录 |
| [docs/direct-build-executor-notes-20260617.md](docs/direct-build-executor-notes-20260617.md) | DirectBuild、reservation、deferred 机制经验 |
| [docs/bot-inheritance.md](docs/bot-inheritance.md) | Sharpy Bot 继承关系和 dummies 说明 |
| [docs/sharpy-overview.md](docs/sharpy-overview.md) | Sharpy 底层框架说明 |
| [docs/sharpy-modules-and-config.md](docs/sharpy-modules-and-config.md) | Sharpy 模块和配置说明 |

## 维护建议

- README 只保留入口级信息；实现细节放到 `docs/system-architecture.md`。
- 策略改动优先同步 `SKILL/terran/<strategy>/Top_agent_<enemy_race>.md` 和 `strategy_tools.py`。
- 新增策略后检查 `registry.json`、运行参数和批量脚本中的 `FORCE_STRATEGY`。
- 修改执行调度后，用短时冒烟对局确认 `.json` 和 `.llm_calls.json` 能正常落盘。
