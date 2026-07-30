# SC2-Agent 测试、检查与修缮指南

本文档是本仓库后续开发者和模型代理的测试入口。目标不是只确认 Python
代码能够启动，而是证明 Terran、Protoss、Zerg 的模型决策、动作映射、
Sharpy 后台策略和 SC2 引擎执行形成了完整闭环。

异常统一记录在同目录的
[`ANOMALY_LOG.md`](./ANOMALY_LOG.md)。任何实战中发现的问题必须先记录，
修复和复测完成后再更新状态，不要只在对话或临时日志中描述。

## 1. 后续模型必须遵守的工作顺序

1. 从仓库根目录执行 `git status -sb`，确认现有修改归属；不得覆盖用户修改。
2. 阅读本指南、`ANOMALY_LOG.md`、相关 `Top_agent.md` 和对应
   `strategy_tools.py`。
3. 在修改前保存可复现证据：命令、种族、策略、模型、对手、地图、游戏时间和
   日志关键行。
4. 在 `ANOMALY_LOG.md` 新增异常，状态先写 `OPEN`。
5. 优先补充一个能够失败的自动化测试，再实施最小范围修复。
6. 依次运行静态检查、完整单元测试、同场景 SC2 复测和至少一个跨种族回归。
7. 只有引擎记录证明问题消失后，才可把异常改为 `FIXED`；仅靠函数返回值或
   “命令已发出”日志不能视为修复完成。
8. 不提交 API 凭据、`API_config/config.json`、`game_records/`、回放或缓存。

## 2. 环境与前置检查

确认 SC2、地图、模型配置和 Git 状态：

```powershell
git status -sb
Test-Path 'C:\Program Files (x86)\StarCraft II'
Get-ChildItem maps -Filter 'KairosJunctionLE*'
python tools\run_experiment.py --help
```

模型配置位于被 Git 忽略的 `API_config/config.json`。禁止在控制台、测试报告
或提交中打印 API Key。

推荐先验证模型模式：

```powershell
python API_Tools\probe_reasoning_extraction.py `
  --model-key Kimi-k2.5 `
  --max-tokens 256

python API_Tools\probe_reasoning_extraction.py `
  --model-key DeepSeek-V4-flash_think `
  --max-tokens 256
```

预期 Kimi 为 non-thinking，DeepSeek thinking 能单独提取 reasoning，且两者的
公开内容都能被正常解析。

## 3. 每次修改后的基础检查

```powershell
python -m compileall -q `
  SC2_Agent `
  dummies\generic `
  sharpy\plans\acts `
  SKILL `
  tools\tests

python -m pytest tools\tests -q -p no:cacheprovider
git diff --check
```

必须全部通过。`git diff --check` 在 Windows 上出现 LF/CRLF 提示不算失败，
但不能出现 trailing whitespace 或 conflict marker。

重点自动化不变量：

- 三个种族的 Registry 与实际策略目录完全一致。
- 每个策略目录只有一个 `Top_agent.md`。
- `Top_agent.md` 只使用一个 `# Summary` 顶级标题。
- 所有目录都能导入 `strategy_tools.py`。
- 模型实体能解析到当前种族的合法 SC2 `AbilityId`、`UnitTypeId` 或
  `UpgradeId`。
- 大小写兼容不能重新引入 `OverlordTransport` 等歧义碰撞。
- Gateway/WarpGate 候选、Archon 双单位合成、Larva 生产和 Zergling 双产出
  必须保留测试。
- 已进入引擎的升级、建造和变形必须成为 commit boundary，不能被新决策取消。

## 4. 三种族短局冒烟测试

每次改动动作映射、调度器、提示词或 Skill 后，至少各跑一场：

```powershell
python tools\run_experiment.py `
  --strategy marine_rush `
  --bot-race terran `
  --enemy-race terran `
  --enemy-difficulty easy `
  --decision-model Kimi-k2.5 `
  --decision-interval 45 `
  --game-time-limit 360 `
  --batch-name smoke_three_races

python tools\run_experiment.py `
  --strategy four_gate `
  --bot-race protoss `
  --enemy-race terran `
  --enemy-difficulty easy `
  --decision-model Kimi-k2.5 `
  --decision-interval 45 `
  --game-time-limit 360 `
  --batch-name smoke_three_races

python tools\run_experiment.py `
  --strategy twelve_pool `
  --bot-race zerg `
  --enemy-race terran `
  --enemy-difficulty easy `
  --decision-model Kimi-k2.5 `
  --decision-interval 45 `
  --game-time-limit 360 `
  --batch-name smoke_three_races
```

不要并行启动多个本地 SC2 客户端。当前
`tools/run_kimi_nothink_strategy_sweep.py` 没有传递 `--bot-race`，在完成该工具
的三种族改造前，不得使用它测试 Protoss 或 Zerg。

## 5. 20 分钟上限完整对局矩阵

“20 分钟测试”应设置 `--game-time-limit 1200`。如果提前摧毁对手并得到
`Victory`，这是正常完成的完整对局，不需要为了凑满时间阻止进攻。

推荐最小矩阵：

| 我方种族 | 策略 | 覆盖目标 |
|---|---|---|
| Protoss | `four_gate` | WarpGate、同步折跃、Blink、地面进攻 |
| Protoss | `robo` | Observer、Immortal、RoboticsBay |
| Protoss | `voidray` | Stargate、FleetBeacon、空军升级 |
| Zerg | `lings` | Larva、Queen、虫狗速度、大批量生产 |
| Zerg | `roach_hydra` | Lair、双兵种、地面升级、三基地 |
| Zerg | `mutalisk` | Spire、飞龙、空军升级和地面支援 |

命令模板：

```powershell
python tools\run_experiment.py `
  --strategy <strategy> `
  --bot-race <protoss|zerg> `
  --enemy-race terran `
  --enemy-difficulty easy `
  --decision-model Kimi-k2.5 `
  --decision-interval 60 `
  --game-time-limit 1200 `
  --batch-name long_regression
```

修改调度器的通用逻辑后，还应选择 DeepSeek thinking 对三个种族各跑一场，
防止修复只适配某一种模型输出风格。

## 6. 对局后必须检查的证据

每场目录应包含：

- 主交互 JSON；
- `*.llm_calls.json`；
- `.SC2Replay`；
- 正常结束信息。

主 JSON 必须满足：

- `dropped_unknown_names` 总数为 0；
- `dropped_unmapped_names` 总数为 0；
- 执行错误总数为 0；
- 每个模型动作都保留 canonical name、实际 action 和 execution mode；
- Kimi 的 `reasoning_content` 为空；
- 已提交工作不会重新出现在可取消队列里。

日志扫描：

```powershell
rg -n -i `
  'Traceback|\bERROR\b|engine rejected|issue failed|No module named|Abandoned stuck RUNNING' `
  game_records\<batch>\runner_logs
```

还要检查后台 Act 是否按条件触发：

- `PlanZoneAttack`：日志必须显示战力超过策略阈值后才出现
  `Attack started`。
- `PlanZoneDefense`：只有基地或防区出现威胁时才应接管单位；未触发不等于失败。
- Protoss：观察 Chrono、WarpGate 转换和实际单位数量增长。
- Zerg：观察 Inject、CreepTumor、Overlord 侦察获得的视野以及 Larva 转化。
- `PlanFinishEnemy`：只有已知基地清空后才接管空闲战斗单位。

“issued” 只表示 Python 接受了命令。必须结合后续 observation、最终单位统计或
Replay，确认单位、建筑、升级和战斗结果真的出现在 SC2 中。

## 7. 策略质量检查

不要只检查胜负。阅读每个决策周期的 observation、reason 和 new queue，并记录：

- 是否重复建造唯一科技建筑；
- 是否无视 `Top_agent.md` 的主力兵种；
- 是否在供应将满时忘记补 Depot、Pylon 或 Overlord；
- 是否长时间缺少工人、Queen、基地或气矿；
- 是否矿气持续大量积压；
- 是否生产建筑数量超过经济承载能力；
- 是否在克制关系发生变化时有合理转型；
- 攻击阈值是否过早送兵或过晚囤兵。

策略摘要应写清：

- 开局核心顺序和不可推迟的关键科技；
- 唯一科技建筑和生产建筑的大致上限；
- 工人/基地饱和与扩张条件；
- 主力与辅助兵种比例；
- 第一波进攻条件和增援方式；
- 资源积压时如何消费；
- 遭遇反制时的有限转型路径。

保持一个 `Top_agent.md`，不要重新拆分成按敌方种族命名的多个 Markdown。

## 8. 从异常到修复的方法

按以下顺序定位，避免用扩大超时或吞异常掩盖根因：

| 现象 | 优先检查 |
|---|---|
| 模型名称被丢弃 | `race_catalog.py`、实体规范化和当前种族过滤 |
| 动作未映射 | `sc2_data_common.py`、`entity_to_actions.py` |
| 一直等待科技 | `prereq_runtime`、等价建筑、升级前置 |
| 命令已发但单位没出现 | producer 选择、人口成本、Larva/WarpGate 特殊路径 |
| 升级被标记卡死 | `already_pending_upgrade` 与实际 UpgradeId |
| 气矿请求超时 | 是否有完成基地和空闲 geyser，gas action 是否保持等待 |
| 重复科技建筑 | 策略摘要约束与 scheduler structure cap |
| 折跃日志很多但单位不增长 | 同帧折跃限制、放置点和 WarpGate 冷却 |
| 资源大量积压 | 策略队列长度、Larva/生产建筑、工人和基地比例 |

修复完成标准：

1. 新增或更新自动化回归测试。
2. 完整 `tools/tests` 通过。
3. 原失败命令复跑后问题消失。
4. 至少一个其他种族没有回归。
5. JSON 中 unknown、unmapped、execution error 均为 0。
6. 异常日志更新为 `FIXED`，写入修复位置和复测证据。

## 9. 提交前检查清单

- [ ] `git status -sb` 中只有本次任务相关文件。
- [ ] 未暂存 `API_config/config.json`、日志、Replay 或缓存。
- [ ] `python -m pytest tools\tests -q -p no:cacheprovider` 通过。
- [ ] `python -m compileall ...` 通过。
- [ ] `git diff --check` 通过。
- [ ] 相关异常记录已更新。
- [ ] 文档命令包含正确的 `--bot-race`。
- [ ] 提交信息能够概括代码、Skill 和测试证据。
