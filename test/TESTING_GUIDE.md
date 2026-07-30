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

不要并行启动多个本地 SC2 客户端。批量工具
`tools/run_kimi_nothink_strategy_sweep.py` 已支持 `--bot-races` 并会把每个 job 的
`--bot-race` 传给运行器；使用前仍应先检查 dry-run/job 列表中的种族、策略和地图，
避免把同名策略路由到错误种族。

## 5. 三种族代表策略测试集

进行全局回归时，不要只跑每个种族最容易获胜的一种策略。下面每个种族选择
5 个玩法不同、技术路线明确且能够覆盖关键引擎机制的代表策略。它们共同组成
标准的 15 策略测试集。

### 5.1 Terran

| 策略 | 代表性与差异 | 测试重点 |
|---|---|---|
| `marine_rush` | 单基地、低科技、纯步兵早期压制 | 快速补给、Barracks 连续生产、低兵力攻击阈值和增援是否及时 |
| `bio` | 多基地 Marine/Marauder/Medivac 生化运营 | BarracksReactor/BarracksTechLab、Stimpack/ShieldWall、Medivac 和中后期扩张是否形成闭环 |
| `blueflame_locks` | Hellion/Cyclone/Thor 机动机械化 | Factory 附件、BlueFlame、CycloneLockOnDamage、双 Armory 升级和气矿需求 |
| `two_base_matrix_tanks` | Tank/Marine/Raven/Liberator 两基地阵地战 | SiegeTank、StarportTechLab、Raven/Liberator、CorvidReactor 和攻防接管 |
| `yamato_rust_fleet` | Battlecruiser/Viking 为核心的重型空军后期 | FusionCore、Yamato、舰船升级、多 Starport、四基地经济和高人口进攻 |

这五项依次覆盖早期步兵、常规生化、机动机械、阵地混编和后期空军。若修改
Terran 附件交换或 producer 选择，必须至少复跑 `bio`、`blueflame_locks` 和
`two_base_matrix_tanks`，不能只用不依赖复杂附件的 `marine_rush` 判定通过。

### 5.2 Protoss

| 策略 | 代表性与差异 | 测试重点 |
|---|---|---|
| `four_gate` | 四门 WarpGate 正面时机压制 | WarpGateResearch、Gateway 变形、同周期折跃、Pylon 供能和 Blink |
| `dark_templar_rush` | TwilightCouncil/DarkShrine 隐形突袭 | 完整科技前置、DarkTemplar 生产、侦测对局下的常规兵转型 |
| `robo` | Observer/Immortal 为核心的地面机械化 | RoboticsFacility、Observer 探测、Immortal、可选 RoboticsBay 和前排配比 |
| `voidray` | 两基地 Stargate 主力空军 | Stargate/FleetBeacon 唯一性、VoidRaySpeed、空军升级和地面掩护 |
| `macro_stalkers` | 双基地 Blink Stalker 机动运营 | Probe 饱和、WarpGateResearch、BlinkTech、Observer 探测和多线换血 |

这五项分别覆盖正面时机、隐形科技、Robotics、Stargate 和 Blink 宏观运营。
修改 Protoss 动作映射后，应特别比较 `four_gate` 与其他四项：只有前者大量使用
WarpGate，同一个单位从 Gateway 与 WarpGate 生产时都必须选择当前可用 producer。

### 5.3 Zerg

| 策略 | 代表性与差异 | 测试重点 |
|---|---|---|
| `twelve_pool` | 低 Drone 数的最早 Zergling 全压 | SpawningPool 前置、Overlord 补给、Larva 消耗、Zergling 双产出和持续增援 |
| `macro_roach` | Roach/Ravager 三基地耐久运营 | Drone 饱和、RoachWarren/Lair、GlialReconstitution、Ravager 变形和重整 |
| `roach_hydra` | Roach 前排加 Hydralisk 远程/防空 | HydraliskDen 前置、两种 Hydra 升级、兵种比例、EvolutionChamber 上限 |
| `lurkers` | Lair 后 Hydralisk 转 Lurker 的高阶地面科技 | LurkerDenMP、Hydralisk morph、LurkerRange、气矿供给和阵地进攻 |
| `mutalisk` | Spire 空军骚扰与地面消费并行 | Spire 唯一性、Mutalisk 批量生产、Flyer 升级归属和矿气分配 |

这五项依次覆盖早期 Larva 爆兵、常规 Roach 运营、混合防空、高阶单位变形和
空军骚扰。修改 Zerg 生产逻辑时，至少同时复跑 `twelve_pool` 和一个两人口单位
策略；Zergling 一枚 Larva 产两只，而 Roach、Hydralisk、Lurker 和 Mutalisk
不能沿用这个数量换算。

### 5.4 测试层级与选择规则

- 日常小修改：从受影响种族选 1 个最直接策略，再从另一个种族选 1 个回归。
- 动作映射、调度器或通用提示词修改：15 个策略全部跑 360 秒短局。
- 种族特有 producer、升级或变形修改：该种族 5 个策略全部跑短局，并选择
  其中至少 2 个跑 1200 秒上限完整对局。
- 发版或声明“三种族可用”前：15 个策略均有最新短局证据；每个种族至少
  2 个不同技术路线有完整对局证据。
- 某策略失败时，先用相同 seed、地图、模型和对手复现，不得直接换成更容易的
  策略来替代该项。

所有 15 个策略都使用各自目录中唯一的 `Top_agent.md`。测试报告应写出实际
读取的文件路径，避免因为 race/strategy 路由错误而误用其他种族的摘要。

## 6. 20 分钟上限完整对局矩阵

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

## 7. 对局后必须检查的证据

每场目录应包含：

- 主交互 JSON；
- `*.llm_calls.json`；
- `.SC2Replay`；
- 正常结束信息。

主 JSON 必须满足：

- `dropped_unknown_names` 总数为 0；
- `dropped_unmapped_names` 总数为 0；
- 执行错误总数为 0；
- observation 的 completed/queue 不得暴露不可生产的引擎形态，例如
  `LIBERATORAG`、`SUPPLYDEPOTLOWERED`、`LURKERMPBURROWED`；
- 每个模型动作都保留 canonical name、实际 action 和 execution mode；
- Kimi 的 `reasoning_content` 为空；
- 已提交工作不会重新出现在可取消队列里。
- worker 的建造 order 只能证明命令在途，不能作为建筑动作 `DONE` 的依据；
  后续 observation 必须出现真实 foundation/under-construction structure。
- 同一决策周期内的多个气矿、普通建筑和扩张动作必须使用互不冲突的 geyser、
  footprint 与 expansion 坐标；不能用一座实体同时满足多个 PA。

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
- `PlanFinishEnemy`：只有已知基地清空后才接管角色层空闲战斗单位；这些单位即使
  刚收到 `PlanZoneGather` 的集结移动订单，也必须能被最终搜索命令接管。

“issued” 或 Sharpy 的 `Started` 只表示 Python 尝试了命令，不是引擎提交证据。
研究至少还要看到后续 SC2 order/upgrade 使 scheduler 输出
`DONE: target already satisfied`；单位、建筑和战斗则必须结合后续 observation、
最终统计或 Replay，确认结果真的出现在 SC2 中。

## 8. 策略质量检查

不要只检查胜负。阅读每个决策周期的 observation、reason 和 new queue，并记录：

- 是否重复建造唯一科技建筑；
- 是否无视 `Top_agent.md` 的主力兵种；
- 是否在供应将满时忘记补 Depot、Pylon 或 Overlord；
- 是否长时间缺少工人、Queen、基地或气矿；
- 是否误以为框架会自动生产工人；用 observation 的 `current/ideal workers`
  判断现有基地饱和度，单轮工人数量通常不超过 current-to-ideal 缺口，同时避免
  后期追逐所有理论槽位而生产 100+ 工人；
- 是否矿气持续大量积压；
- 矿产超过约 1000 时是否仍只加工人、基地或无关科技，而没有增加可立即生产的
  主力单位及足够的生产能力；
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

## 9. 从异常到修复的方法

按以下顺序定位，避免用扩大超时或吞异常掩盖根因：

| 现象 | 优先检查 |
|---|---|
| 模型名称被丢弃 | `race_catalog.py`、实体规范化和当前种族过滤 |
| 动作未映射 | `sc2_data_common.py`、`entity_to_actions.py` |
| 一直等待科技 | `prereq_runtime`、等价建筑、升级前置 |
| 命令已发但单位没出现 | producer 选择、人口成本、Larva/WarpGate 特殊路径 |
| 升级被标记卡死 | `already_pending_upgrade` 与实际 UpgradeId |
| 气矿请求超时 | 是否有完成基地和空闲 geyser，gas action 是否保持等待 |
| 建造动作 DONE 但建筑未出现 | 是否误把 worker en-route order 当成 foundation；订单消失后 PA 是否能重试 |
| 同轮多个建筑只有一个形成 | 跨 Act 的 geyser/footprint/expansion 预留是否共享并在确认窗口后释放 |
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

## 10. 提交前检查清单

- [ ] `git status -sb` 中只有本次任务相关文件。
- [ ] 未暂存 `API_config/config.json`、日志、Replay 或缓存。
- [ ] `python -m pytest tools\tests -q -p no:cacheprovider` 通过。
- [ ] `python -m compileall ...` 通过。
- [ ] `git diff --check` 通过。
- [ ] 相关异常记录已更新。
- [ ] 文档命令包含正确的 `--bot-race`。
- [ ] 提交信息能够概括代码、Skill 和测试证据。
