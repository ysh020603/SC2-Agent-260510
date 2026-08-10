# SC2-Agent 异常与修缮记录

本文件是可持续追加的测试账本。后续模型发现异常时，先在顶部表格新增一行，
再在下方添加详情。不得删除历史异常；误报应标记 `CLOSED-NOT-A-BUG` 并解释。

状态定义：

- `OPEN`：已复现，尚未修复。
- `IN-PROGRESS`：已有修复，但尚未完成 SC2 引擎复测。
- `FIXED`：自动化与对应 SC2 场景均已验证。
- `MONITORING`：已缓解，但需要更多地图、对手或模型数据。
- `CLOSED-NOT-A-BUG`：符合预期条件触发规则。

## 异常索引

| ID | 日期 | 状态 | 范围 | 摘要 |
|---|---|---|---|---|
| SC2-034 | 2026-07-30 | FIXED | 分层 Prompt / 策略上下文 | DeepSeek 缩写升级名并把自动 WarpGate morph 当成宏任务 |
| SC2-033 | 2026-07-30 | FIXED | Expand/BuildGas 生命周期 | Act 已发 worker command 但返回 False，队列替换会丢失未落地建筑的重试所有者 |
| SC2-032 | 2026-07-30 | FIXED | Terran 直接建造 | direct-build 把 SCV en-route order 当作 DONE，工人中断后无法重试 |
| SC2-031 | 2026-07-30 | FIXED | 建筑提交边界 | worker en-route order 被当作 DONE，订单中断后建筑永远不形成 |
| SC2-030 | 2026-07-30 | FIXED | 后台动作 | PlanCancelBuilding 对不可取消的成长中 CreepTumor 反复发送 cancel |
| SC2-029 | 2026-07-30 | FIXED | 三族扩张 | 多个 Expand 实例在引擎回报前可重复选择同一 expansion zone |
| SC2-028 | 2026-07-30 | FIXED | 三族建筑落点 | 不同 GridBuilding 实例同帧可选择重叠 footprint，SC2 只能接受其中一项 |
| SC2-027 | 2026-07-30 | OPEN | 决策契约 | 模型把队列顺序误当 timing lock，并在卡人口时一次请求 20 Overlord |
| SC2-026 | 2026-07-30 | FIXED | 三族气矿 | 同帧重复 gas action 选择同一 geyser，单座建筑错误满足多个任务 |
| SC2-024 | 2026-07-30 | FIXED | 测试入口 | 文档中的 pytest 命令在干净环境找不到内置 python-sc2 |
| SC2-025 | 2026-07-30 | FIXED | LLM 上下文 | 观察暴露 LIBERATORAG 等不可生产的引擎形态，模型会原样回填为 unknown |
| SC2-023 | 2026-07-30 | FIXED | Terran 补给 | direct build 在完成确认前先执行超时清理，已完成任务偶发 stuck abandon |
| SC2-022 | 2026-07-30 | FIXED | Windows sweep | sweep 向 Windows 子进程注入 Linux SC2PATH，所有对局启动失败 |
| SC2-021 | 2026-07-30 | MONITORING | 终局搜索 | PlanZoneGather 的移动订单使 PlanFinishEnemy 找不到引擎 idle 部队 |
| SC2-020 | 2026-07-30 | FIXED | 三族经济 | 模型误以为工人自动生产，或追逐 ideal 生产 100+ 工人并大量积压资源 |
| SC2-019 | 2026-07-30 | FIXED | 研究提交 | Sharpy Started 后无 SC2 订单，研究长期伪 RUNNING 后被放弃 |
| SC2-018 | 2026-07-30 | FIXED | Protoss 落点 | `macro_stalkers` 对 T@Kairos 大量 Gateway/ShieldBattery/Stargate 无落点 |
| SC2-017 | 2026-07-30 | FIXED | Zerg 实体名 | 模型输出复数 `Extractors` 被 unknown 丢弃 |
| SC2-016 | 2026-07-30 | FIXED | Protoss 实体名 | 全大写升级名 `PROTOSSGROUND*LEVEL1` 被 unknown，合法名为 PascalCase |
| SC2-015 | 2026-07-30 | FIXED | 测试基建 | 并发 runner 写同一 runner_logs 文件时 PermissionError，矩阵进程异常退出 |
| SC2-014 | 2026-07-30 | FIXED | Terran 实体名 | 模型输出 `TechLab`/`CombatShield` 被判 unknown 丢弃，合法名应为附属建筑/`ShieldWall` |
| SC2-013 | 2026-07-30 | FIXED | Terran 附件 | Barracks/Factory/Starport 的 TechLab/Reactor 反复找不到落点并 stuck abandon |
| SC2-012 | 2026-07-30 | FIXED | 记录路径 | 默认 match_id + batch 在 Windows 上超过 MAX_PATH，日志文件创建失败 |
| SC2-001 | 2026-07-29 | FIXED | 三种族映射 | 大小写回退可能把同名实体映射到错误类别 |
| SC2-002 | 2026-07-29 | FIXED | 三种族气矿 | Assimilator/Extractor 没有统一走 BuildGas |
| SC2-003 | 2026-07-29 | FIXED | Protoss | Gateway 与 WarpGate 候选选择错误 |
| SC2-004 | 2026-07-29 | FIXED | Protoss | 同一帧多个折跃命令发生落点冲突 |
| SC2-005 | 2026-07-29 | FIXED | Zerg | Zergling 双产出与实际人口成本处理不正确 |
| SC2-006 | 2026-07-30 | FIXED | 研究调度 | 已开始升级仍被判定 stuck RUNNING |
| SC2-007 | 2026-07-30 | FIXED | 气矿调度 | 暂无空闲 geyser 时气矿动作被超时放弃 |
| SC2-008 | 2026-07-30 | FIXED | 策略/执行 | 模型重复请求唯一科技建筑 |
| SC2-009 | 2026-07-30 | FIXED | 策略知识 | Mutalisk 摘要错误地暗示 EvolutionChamber 负责空军升级 |
| SC2-010 | 2026-07-30 | MONITORING | 策略经济 | 部分虫族策略矿气积压过高 |
| SC2-011 | 2026-07-30 | FIXED | 批量工具 | strategy sweep 未传递 bot-race，只适合当前默认种族 |

## 详细记录

### SC2-001：实体名称歧义

- 现象：不区分大小写的全局回退可能在 Unit、Upgrade 等类别间选择错误实体，
  `OverlordTransport` 是已观察到的碰撞样例。
- 根因：回退索引允许一个折叠名称对应多个候选。
- 修复：精确名称优先；只有大小写折叠结果唯一时才允许回退。
- 验证：三种族 catalog 自动化测试和真实模型动作映射均为 0 unknown /
  0 unmapped。

### SC2-002：三种族气矿执行路径

- 现象：Refinery 之外的气矿建筑可能被当作普通 GridBuilding。
- 根因：执行映射只覆盖 Terran 特例。
- 修复：Refinery、Assimilator、Extractor 全部交给 `BuildGas`。
- 验证：catalog 测试检查三个目标，Protoss/Zerg 实战均成功完成气矿。

### SC2-003：Gateway/WarpGate 选择

- 现象：WarpGate 已空闲时，调度器仍可能选择剩余 Gateway 训练。
- 根因：候选按原始动作顺序选择，没有优先实时可用的 WarpGate。
- 修复：存在可用 WarpGate 时优先 `warp_in` 候选，同时保留 Gateway 回退。
- 验证：实战中 Gateway 转换后 Stalker/Adept 数量实际增长。

### SC2-004：同帧折跃冲突

- 现象：多个折跃命令可能在同一 Python-SC2 帧使用同一放置点，日志显示 issued，
  但最终只落地部分单位。
- 修复：每帧最多发出一个折跃命令，其余计划等待下一帧重新计算位置。
- 验证：Protoss 专项回归中 Stalker 从 4 增长到 7，后续 Adept 长局持续落地。

### SC2-005：虫族双产出和人口

- 现象：一次 Zergling Larva 动作生成两个单位，固定人口计算会错误阻塞或超发。
- 修复：catalog 保存 `output_count=2`，调度器按真实目标单位计算人口成本。
- 验证：十二池与 lings 长局分别生产 38 和 64 条 Zergling。

### SC2-006：升级 commit boundary

- 现象：ProtossAirWeaponsLevel1、EvolveMuscularAugments 等已经在 SC2 中研究，
  计划仍在 25 秒后出现 `Abandoned stuck RUNNING`。
- 根因：审核动作的 AbilityId 与建筑订单中的通用研究 AbilityId 不一定相同。
- 修复：以 UpgradeId 调用 `BotAI.already_pending_upgrade` 作为权威提交状态。
- 自动化：`test_pending_upgrade_id_is_an_engine_commit_boundary`。
- 复测：VoidRay、Roach-Hydra 修复场均在 `Started ...` 后立即记录
  `DONE: target already satisfied`，没有再次超时。

### SC2-007：气矿等待

- 现象：基地尚未完成或当前 geyser 已占用时，新的 Assimilator 请求可能在 25 秒后
  被视为无落点并放弃。
- 根因：气矿与普通不可放置建筑共用 RUNNING abandon 规则。
- 修复：三个种族的气矿动作作为 sticky build 等待可用 geyser。
- 自动化：`test_gas_build_waits_for_a_free_geyser_instead_of_being_abandoned`。
- 复测：VoidRay 修复场中 Assimilator 正常提交且无 stuck 记录。

### SC2-008：重复科技建筑

- 现象：长局中模型即使在 reason 中知道“科技建筑过多”，之前排入引擎的增量动作
  仍造成 4 个 EvolutionChamber 或额外 CyberneticsCore。
- 根因：每个建筑名称具有增量语义，单靠自然语言摘要无法保证模型不重复请求。
- 修复：
  - 神族唯一科技建筑上限 1，Forge 上限 2；
  - 虫族唯一科技建筑上限 1，EvolutionChamber 上限 2；
  - 生产建筑保持不设上限；
  - 统计 worker en-route，避免缓存出现建筑前连续下单。
- 自动化：`test_technology_structure_target_count_is_capped`。
- 复测：最终 Roach-Hydra 场只有 2 个 EvolutionChamber 和各 1 个关键科技建筑。

### SC2-009：飞龙升级知识错误

- 现象：旧摘要让模型为 flyer upgrades 建造 EvolutionChamber。
- 根因：策略文本混淆了地面升级和 Spire 空军升级。
- 修复：明确 ZergFlyerWeapons/ZergFlyerArmors 在 Spire 研究，EvolutionChamber
  只服务地面支援部队。
- 复测：Mutalisk 长局完成 Spire、12 个 Mutalisk 和空军升级队列。

### SC2-010：虫族资源积压

- 现象：初次 lings 与 Roach-Hydra 长局出现最高 1700–2955 矿、平均余矿
  800 以上。
- 修复：摘要加入 Larva 不足时补 Queen/Hatchery、矿产阈值、兵种比例、扩张和
  转型规则。
- 当前证据：最终 Roach-Hydra 场最高余矿 640、平均余矿 115。
- 状态说明：Easy AI 会较早结束，仍需在 Medium/Hard 和不同地图监控 15–20
  分钟经济曲线，因此保留 `MONITORING`。

### SC2-011：多种族 sweep 参数缺失

- 状态：FIXED（2026-07-30）
- 现象：`tools/run_kimi_nothink_strategy_sweep.py` 调用
  `tools/run_experiment.py` 时没有传递 `--bot-race`。
- 风险：用该 sweep 测 Protoss/Zerg 策略时会使用 `run_experiment.py` 的默认
  Terran，从而产生无效结果。
- 修复：sweep 新增 `--bot-races`，把我方种族写入 `MatchJob`、match id 和
  `run_experiment.py --bot-race`；不存在的 race/strategy 组合直接报错，不静默跳过。
  Windows 子进程不再注入 Linux 专用的默认 `SC2PATH`。
- 自动化测试：`tools/tests/test_strategy_sweep.py` 覆盖三族命令矩阵、缺失策略和
  Windows 环境继承。
- SC2 复测：`optall730_t`、`optall730_p2`、`optall730_z2` 均由同一 sweep
  按指定我方种族启动。

### SC2-012：Windows 记录路径超长导致对局无法启动

- 日期：2026-07-30
- 状态：FIXED（2026-07-30）
- 环境：分支 `SC2-Agent-knowlegde`；Windows 10；batch
  `kimi_nothink_full_matrix_20260730`；模型 `Kimi-k2.5`；策略
  `marine_rush` 等；地图 `KairosJunctionLE` 等
- 复现命令：
  `python tools\run_experiment.py --strategy marine_rush --bot-race terran --enemy-race terran --enemy-difficulty easy --decision-model Kimi-k2.5 --decision-interval 60 --game-time-limit 1200 --map-name KairosJunctionLE --batch-name kimi_nothink_full_matrix_20260730 --run-index 0`
- 预期：`run_vs_ai` 创建记录目录后成功写入 `.log` 并启动 SC2。
- 实际：目录可创建（约 184 字符），但日志完整路径约 274 字符，超过
  Windows 传统 `MAX_PATH`（260），`loguru`/`open` 抛出
  `FileNotFoundError`，对局在启动 SC2 前退出。
- 日志/JSON/Replay 证据：空 match 目录已创建但无 `.log` / JSON /
  Replay；runner 在约 1–2 秒内 `exit=1`。
- 根因：默认 `match_id` 含 bot/race/difficulty/map/model/interval 等长字段，
  再叠加长 `batch-name` 与同名日志文件，路径长度失控；`game_starter`
  写日志前未确保父路径可用、也未做长度防护。
- 修复文件：`run_vs_ai.py` 使用保留完整身份输入的短摘要 match id；
  `bot_loader/game_starter.py` 在唯一 match 目录内使用固定 `match` 文件名，
  不再把长 match id 重复写入每个 artifact。
- 自动化测试：`tools/tests/test_experiment_paths.py` 覆盖长 batch/match 路径。
- SC2 复测：batch `kimi_nothinking_optimization_validation_20260730` 成功写入
  `match.log/json/llm_calls/SC2Replay`，最长 artifact 路径 185 字符。
- 跨种族回归：三种族默认 id 均受影响。
- 备注：当前完整对局矩阵改用短 batch `kn30` 与 `--match-prefix` 规避，
  以便继续收集策略/引擎证据。

### SC2-013：人族附件（TechLab/Reactor）无法落点并 stuck abandon

- 日期：2026-07-30
- 状态：FIXED（2026-07-30）
- 环境：`Kimi-k2.5`；batch `kn30`；Easy Terran AI；完整对局上限 1200s
- 复现命令：
  - `bio` / AutomatonLE：`run1` 目录 `20260730_130115_t_bio_au_run1`
  - `two_base_matrix_tanks` / AbyssalReefLE：`run2` 目录
    `20260730_130701_t_2bmt_ab_run2`
- 预期：有空闲 Barracks/Factory/Starport 时，`BarracksTechLab` /
  `BarracksReactor` / `FactoryTechLab` / `StarportTechLab` 能挂上附件并解锁
  Stim/Marauder/Tank/Raven 等科技闭环。
- 实际：日志大量 `Can't find free position to build ...TECHLAB/REACTOR`，随后
  `Abandoned stuck RUNNING action BUILD_TECHLAB_* / BUILD_REACTOR_* after 25s`。
  - bio：NO_POS BarracksReactor 254、BarracksTechLab 248；abandon 7；Defeat 11:40
  - two_base_matrix_tanks：NO_POS BarracksTechLab 555、StarportTechLab 330、
    FactoryTechLab 285；abandon 24；Tie 20:00
- 日志/JSON/Replay 证据：上述 match 目录下 `.log` / `.json` / `.SC2Replay`
- 根因：race catalog 先把附件 action 误分类成 `worker_build`，scheduler 因而
  用地图建筑 `GridBuilding` 为 TechLab/Reactor 寻找独立落点。
- 修复文件：`race_catalog.py` 与 `execution/mapping.py` 把附件归为 `addon`；
  `build_addon.py` 排除同帧已收到其他命令的生产建筑。
- 自动化测试：覆盖所有 reviewed addon action 的分类、Act 类型以及同帧 producer
  互斥。
- SC2 复测：`optall730_t` 五场中 Barracks/Factory/Starport TechLab 与 Reactor
  均实际完成，附件 NO_POS 为 0，五策略全部 Victory。
- 跨种族回归：Protoss/Zerg 本批无同类附件问题
- 备注：`marine_rush`（无附件）无此现象；问题集中在需要 TechLab/Reactor 的人族策略

### SC2-014：人族别名 `TechLab` / `CombatShield` 被丢弃

- 日期：2026-07-30
- 状态：FIXED（2026-07-30）
- 环境：同上；`bio` 与 `two_base_matrix_tanks`
- 复现命令：同 SC2-013 的 run1 / run2
- 预期：`dropped_unknown_names` 总数为 0；战斗盾牌应映射到 `ShieldWall`，
  TechLab 应映射到具体 `BarracksTechLab`（或等价附属实体）
- 实际：
  - bio：`dropped_unknown_names` 含 `TechLab`×1、`CombatShield`×1
  - two_base_matrix_tanks：`CombatShield`×3
  - 数据库/映射侧权威升级名为 `ShieldWall`（ability `RESEARCH_COMBATSHIELD`）
- 日志/JSON/Replay 证据：主 JSON 中 `dropped_unknown_names`
- 根因：catalog/别名表未接受常见口语名；部分 `Top_agent.md` 与
  `TESTING_GUIDE.md` 也写 `CombatShield`，会强化错误输出
- 修复文件：catalog 加入经审查的 `CombatShield/CombatShields -> ShieldWall`
  别名；所有 Terran 摘要与测试指南改用具体
  `BarracksTechLab/FactoryTechLab/StarportTechLab`，裸 `TechLab` 因有歧义继续拒绝。
- 自动化测试：覆盖 ShieldWall 别名以及裸 TechLab 拒绝。
- SC2 复测：`optall730_t` 五场 unknown/unmapped 均为 0；bio 实际完成
  Stimpack 与 ShieldWall。
- 跨种族回归：无
- 备注：与 SC2-013 叠加后，人族生化/坦克策略科技闭环更难形成

### SC2-015：并发矩阵 runner 日志 PermissionError

- 日期：2026-07-30
- 状态：FIXED（2026-07-30）
- 环境：`test/_run_full_matrix_concurrent.py`，concurrency=5，batch `kn30`
- 复现命令：`python test\_run_full_matrix_concurrent.py`
- 预期：5 局并发结束后打印 `finished: failures=...` 并正常退出
- 实际：约 8 分钟后以
  `PermissionError: ... runner_logs\03_protoss_four_gate_AutomatonLE.log`
  崩溃（exit=1）；父进程退出时部分 job 完成状态未汇总
- 日志/JSON/Replay 证据：终端 899959；对局记录本身多数仍已落盘
- 根因：重复运行复用了固定 runner 日志名，旧进程/句柄与新一轮并发写入冲突。
- 修复文件：三个本地矩阵 runner 均使用 `timestamp_pid` session 目录，使每轮、
  每 job 的日志路径唯一。
- SC2 复测：后续三族并发 sweep 正常汇总退出，未再出现 PermissionError。
- 跨种族回归：无
- 备注：本批 7 个 run-index 均已有有效主 JSON，可继续做异常分析

### SC2-013 补充（k15 全矩阵）

- 日期：2026-07-30
- batch `k15`：15 策略 × 3 敌族，`Kimi-k2.5`，Easy，地图轮换
- 全局 NO_POS：`BARRACKSTECHLAB` 5093、`FACTORYTECHLAB` 2927、
  `STARPORTTECHLAB` 1729、`BARRACKSREACTOR` 1523
- 全局 abandon 最高：`BUILD_TECHLAB_BARRACKS` 94、`BUILD_TECHLAB_FACTORY` 54、
  `BUILD_TECHLAB_STARPORT` 31、`BUILD_REACTOR_BARRACKS` 27
- 覆盖策略：`bio`、`blueflame_locks`（3 敌全败）、`two_base_matrix_tanks`（3 敌全 Tie）、
  `yamato_rust_fleet`；`marine_rush` 仍基本无附件问题
- 证据：`game_records/k15/runner_logs/analysis_summary.json`

### SC2-014 补充（k15 全矩阵）

- `CombatShield` 在 k15 全局被丢弃 **23** 次，出现在 bio / two_base_matrix_tanks /
  yamato_rust_fleet 多场
- 合法升级名仍为 `ShieldWall`

### SC2-016：神族全大写升级名被丢弃

- 日期：2026-07-30
- 状态：FIXED（2026-07-30）
- 环境：batch `k15`；`four_gate` vs zerg @ AbyssalReefLE（run17，Victory 16:07）
- 复现命令：
  `python tools\run_experiment.py --strategy four_gate --bot-race protoss --enemy-race zerg --enemy-difficulty easy --decision-model Kimi-k2.5 --decision-interval 60 --game-time-limit 1200 --map-name AbyssalReefLE --batch-name k15 --match-prefix pfourgARz --run-index 17`
- 预期：`dropped_unknown_names=0`；地面升级使用
  `ProtossGroundWeaponsLevel1` / `ProtossGroundArmorsLevel1`
- 实际：模型输出 `PROTOSSGROUNDWEAPONSLEVEL1`、`PROTOSSGROUNDARMORSLEVEL1` 被
  unknown 丢弃；同场还有 `FORGERESEARCH_PROTOSSGROUNDARMORLEVEL2` abandon 1 次
- 日志/JSON/Replay 证据：`game_records/k15/*_run17`
- 根因：大小写/别名归一化未接受全大写 UpgradeId 风格
- 修复文件：race catalog 接受仅大小写不同且在当前种族内唯一的 canonical 名称；
  仍拒绝跨种族或多义词。
- 自动化测试：覆盖 Protoss 全大写升级名到唯一 canonical 名的折叠。
- SC2 复测：`optall730_p2` 的 four_gate 与 macro_stalkers 均 Victory，
  unknown/unmapped/abandon 为 0。
- 跨种族回归：人族 `CombatShield`（SC2-014）同类别名问题
- 备注：本场仍 Victory，但升级闭环可能残缺

### SC2-017：虫族复数 `Extractors` 被丢弃

- 日期：2026-07-30
- 状态：FIXED（2026-07-30）
- 环境：batch `k15`；`mutalisk` vs zerg @ AbyssalReefLE（run44，Tie 20:00）
- 复现命令：
  `python tools\run_experiment.py --strategy mutalisk --bot-race zerg --enemy-race zerg --enemy-difficulty easy --decision-model Kimi-k2.5 --decision-interval 60 --game-time-limit 1200 --map-name AbyssalReefLE --batch-name k15 --match-prefix zmutalARz --run-index 44`
- 预期：气矿请求使用 `Extractor`；unknown=0
- 实际：`dropped_unknown_names` 含 `Extractors`×2；另有
  `RESEARCH_ZERGFLYERARMORLEVEL2` abandon 1
- 日志/JSON/Replay 证据：`game_records/k15/*_run44`
- 根因：模型输出英语复数，catalog 仅接受单数实体名
- 修复文件：加入经审查的 `Extractors -> Extractor`（以及三族对应气矿复数）
  别名；Zerg 策略摘要统一改写为 “copies of Extractor”。
- 自动化测试：覆盖 Extractors/Assimilators/Refineries 的种族限定归一化。
- SC2 复测：`optz730` 五场 Zerg unknown/unmapped 均为 0，mutalisk
  在 11:21 Victory 且完成 20 Mutalisks。
- 跨种族回归：检查 `Refineries`/`Assimilators` 是否同类风险
- 备注：同策略对 T/P 均为 Victory 且无此 unknown

### SC2-018：`macro_stalkers` Gateway 等建筑无落点

- 日期：2026-07-30
- 状态：FIXED（2026-07-30）
- 环境：batch `k15`；`macro_stalkers` vs terran @ KairosJunctionLE
  （run27，Tie 20:00）
- 复现命令：
  `python tools\run_experiment.py --strategy macro_stalkers --bot-race protoss --enemy-race terran --enemy-difficulty easy --decision-model Kimi-k2.5 --decision-interval 60 --game-time-limit 1200 --map-name KairosJunctionLE --batch-name k15 --match-prefix pmacroKJt --run-index 27`
- 预期：有空位时 Gateway/ShieldBattery/Stargate 可正常放置
- 实际：NO_POS `GATEWAY` 599、`SHIELDBATTERY` 57、`STARGATE` 56；
  abandon 含 `PROTOSSBUILD_GATEWAY`×8 等；对 P/Z 同策略无此现象且 Victory
- 日志/JSON/Replay 证据：`game_records/k15/*_run27`
- 根因：Protoss `GridBuilding` 只使用静态 solver 的前三组格位，后期格位耗尽后
  没有向已完成 Pylon 周围请求引擎合法落点；也未验证静态点当前仍受供能且可放置。
- 修复文件：`grid_building.py` 对静态点做实时 `can_place`/供能/在途占用检查，
  耗尽后使用 SC2 `find_placement` 在 ready Pylon 与基地周围确定性扩展。
- 自动化测试：`test_protoss_build_placement.py` 覆盖静态格位耗尽后的供能扩展。
- SC2 复测：Kairos `macro_stalkers` 在 `optp730` 9:34 Victory，7 Gateway
  加 2 在建且 NO_POS=0；`optall730_p2` 再次 7:20 Victory、NO_POS=0。
- 跨种族回归：人族附件 SC2-013 同属落点失败族
- 备注：对 P/Z 正常，可能是地图+对局态势组合触发

## k15 矩阵总览（2026-07-30）

- 命令：`python test\_run_15x3_matrix.py`
- 结果：`failures=0/45`；胜负 `Victory 29 / Defeat 6 / Tie 10`
- 虫族 5 策略对三族整体健康（仅 twelve_pool vs Z 败、mutalisk vs Z 平）
- 神族整体健康；`dark_templar_rush`/`robo`/`voidray` 对三族全胜
- 人族依赖附件的策略（bio/blueflame/matrix tanks/yamato）问题集中，见 SC2-013/014
- 分析摘要：`game_records/k15/runner_logs/analysis_summary.json`

### SC2-019：研究命令未获引擎确认却保持 RUNNING

- 日期：2026-07-30
- 状态：FIXED
- 现象：`optall730_t` 中日志出现 `Started RAVENCORVIDREACTOR` /
  `Started TERRANVEHICLEANDSHIPARMORSLEVEL1`，但后续没有对应 SC2 订单或升级，
  25 秒后以 stuck RUNNING abandon。
- 根因：旧 `Tech.execute()` 把调用 `Unit(ability)` 当成已提交；调度器没有先确认
  该生产者当前的 live available ability，也没有在下一帧要求 SC2 order/upgrade
  作为 commit boundary。
- 修复：研究改为调度器直接查询 `get_available_abilities`、确定真实可执行 producer，
  发出命令后进入短暂确认态；未确认回到 WAITING，确认到订单/升级才 DONE。
- 自动化测试：覆盖 live producer 选择、等待引擎确认、未确认回 WAITING 和 busy
  producer 保留。
- SC2 证据：`optall730_z2` 的 Glial、GroovedSpines、MuscularAugments、
  FlyerWeapons 等均由直接路径发出并由后续 SC2 状态确认 DONE。
  `optresearch730` 复跑 blueflame_locks 与 two_base_matrix_tanks，确认
  Stimpack、ShieldWall、VehicleWeapons 和原异常
  VehicleAndShipPlatingLevel1 等研究，研究 abandon 为 0，两场均 Victory。

### SC2-020：工人责任不清与后期工人过量

- 日期：2026-07-30
- 状态：FIXED
- 现象：旧 Protoss DT/four_gate 场仅生产 13/18 Probe；加入“按 ideal 补工人”
  后，Terran blueflame 场又追逐所有理论槽位生产到 102 SCV，并积压上万矿。
- 根因：全局 prompt 只写了补给不自动管理，却没有说明工人生产也必须由模型显式
  请求；“runtime chooses workers”还有被理解为自动生产的歧义。ideal 是已有所有
  矿气槽位总数，不应无限追逐。
- 修复：明确 Worker production NOT automatic、current/ideal 的饱和判断、三族
  后期实用上限，以及矿产超过约 1000 时优先军队与足够生产能力而非继续工人/
  基地/奢侈科技。
- 自动化测试：决策 prompt 合同覆盖工人责任、75% 判断、后期上限和高矿消费。
- SC2 复测：`optall730_p2` 五策略全胜；DT/four_gate Probe 增至 26/31，平均余矿
  316/180。`optfix730` macro_roach 从 20:00 Tie 改为 8:22 Victory。

### SC2-021：集结订单阻断最终搜索

- 日期：2026-07-30
- 状态：MONITORING
- 现象：已知敌方基地清空后，PlanZoneAttack 交给 PlanFinishEnemy；但前一项
  PlanZoneGather 每帧给角色层 idle 部队下移动命令，导致 `ai.units.idle` 为空，
  大军可能长期停在集结点，无法搜索未侦察的残余基地。
- 根因：两个后台 Act 对“idle”的定义不一致：角色 idle 不等于 SC2 引擎无订单。
- 修复：PlanFinishEnemy 改用 `roles.idle`，并在终局阶段覆盖此前的 gather 命令；
  工人及非战斗单位仍由 `unit_values.should_attack` 排除。
- 自动化测试：构造“角色 idle、引擎已有移动订单”的 Roach，确认最终搜索会下达
  attack 并切换到 Attacking 角色。
- SC2 回归：三族批次均能正常触发主进攻并结束；仍需保留一次“敌方藏建筑”的
  专门 Replay 作为终局搜索证据，因此标记 MONITORING。

### SC2-022：Windows sweep 注入错误 SC2PATH

- 日期：2026-07-30
- 状态：FIXED
- 现象：首次多种族 sweep 五场均在启动前失败，子进程尝试使用
  `/data2/StarCraftII`。
- 根因：批量工具无条件注入 Linux 默认 `SC2PATH`，覆盖 Windows 注册表/默认安装
  发现。
- 修复：仅在非 Windows 且调用环境没有显式 SC2PATH 时设置 Linux 默认值。
- 自动化测试：覆盖 Windows 环境继承；后续 `optall730_t/p2/z2` 均成功启动。

### SC2-023：SupplyDepot 在途订单消失后被放弃

- 日期：2026-07-30
- 状态：FIXED
- 现象：`optall730_t` 的后期场次偶发 `TERRANBUILD_SUPPLYDEPOT` 已派 SCV 后没有
  形成建筑，25 秒后 stuck RUNNING abandon；常见于高人口、前线变化或 worker
  订单中断时。
- 根因：调度器每帧先执行 stuck timeout，再异步执行 direct-build 的完成确认。
  当同一队列中的兄弟任务已经满足目标数量时，sticky 判定又会认为无需重试，
  因此一个实际上已经完成的任务可能在确认前被标成 abandon。SupplyDepot 未在
  sticky 集合中会进一步放大在途订单中断问题。
- 修复：超时清理前先同步检查 direct-build 的真实目标是否已满足，满足则直接
  DONE；仍未满足的 SupplyDepot 进入 strategic build retry，重新选择工人和合法
  落点，而不是静默丢弃。
- 自动化测试：覆盖 SupplyDepot sticky 判定，以及“兄弟任务已满足目标时应 DONE、
  不得 abandon”的超时顺序。
- SC2 复测：`optsupply731` 的 15 分钟 two_base_matrix_tanks 场中反复完成
  SupplyDepot、Barracks、Factory、Starport，`ABANDON=0`、`NO_POS=0`、
  `Traceback/ERROR=0`。该场以时间上限 Tie 结束，但目标是超时/完成边界验证，
  构造和确认链路均正常。

### SC2-024：文档 pytest 命令找不到内置 python-sc2

- 日期：2026-07-30
- 状态：FIXED
- 现象：在未预设 `PYTHONPATH` 的 PowerShell 中执行测试指南命令
  `python -m pytest tools\tests -q`，collection 阶段报
  `ModuleNotFoundError: No module named 'sc2'`。
- 根因：`pytest.ini` 的 `python_paths` 依赖非必装插件，不能保证干净环境加载仓库内
  `python-sc2`。
- 修复：新增 `tools/tests/conftest.py`，只为测试进程显式加入 repository root 与
  bundled `python-sc2`。
- 复测：清除当前进程 `PYTHONPATH` 后运行文档原命令，当前为 `71 passed`。

### SC2-025：观察暴露不可生产的引擎形态

- 日期：2026-07-30
- 状态：FIXED
- 现象：`optsupply731` 第 10 轮观察中出现已完成 `LIBERATORAG`，Kimi 随后把
  `LiberatorAG` 放进生产队列；名称校验正确地将其记为 unknown，但这条无效请求
  是框架上下文本身诱发的。相同风险还包括 `SUPPLYDEPOTLOWERED`、
  `SIEGETANKSIEGED`、`LURKERMPBURROWED`、`WARPPRISMPHASING` 等。
- 根因：观察记录器直接使用 python-sc2 的 `UnitTypeId.name`，没有区分可由宏观
  决策生产的实体与同一单位的战术模式/变形壳。
- 修复：在生成 completed、under-construction、workers-en-route 和 active-queue
  上下文时，将战术模式及 morph cocoon 映射回可请求的实体；保留
  BarracksTechLab 等真实独立宏观实体，不用宽泛的字符串猜测或 unknown 兜底。
- 自动化测试：覆盖 Terran/Protoss/Zerg 的典型形态折叠，并确认独立 add-on 与
  OverlordTransport 不会被错误合并。

### SC2-026：重复 gas action 争用同一 geyser

- 日期：2026-07-30
- 状态：FIXED
- 现象：`optlurker732` 在 08:17 同帧把三个 Extractor 工人命令全部发往
  `(136.5, 23.5)`，随后三个 PA 都被同一份“已有/在建”进度标为 DONE。
- 根因：每个重复 PA 在同一 SC2 observation frame 内都计算出相同绝对目标数；
  多个独立 `BuildGas` 实例也看不到兄弟实例刚发出的 worker order，因此都选择
  同一个尚未被下一帧状态占用的 geyser。
- 修复：同一队列的重复建筑 PA 使用递增的绝对目标数；所有 `BuildGas` 实例按
  `game_loop` 共享 geyser tag 预留，第一条命令发出时立即占用该目标，下一帧才
  清空预留。没有通过吞掉重复项或把任务提前标 DONE 取巧。
- 自动化测试：确认从已有 1 座气矿开始的三项请求目标依次为 2/3/4，并确认同帧
  预留跨实例可见、下一帧自动重置。
- SC2 复测：`optlurker738` 同轮两个 Extractor 分别选择 `(63.5,120.5)` 与
  `(67.5,124.5)`，最终统计 4 座 Extractor；全场没有重复 geyser 目标。

### SC2-027：队列优先级被误当成严格时序

- 日期：2026-07-30
- 状态：OPEN
- 现象：旧潜伏者回归中，模型把 Extractor 放在 Hatchery/SpawningPool 后面，
  以为会顺序执行；scheduler 为避免队首阻塞会让可负担的后项越过 waiter，结果
  00:05 就先造气矿。另一轮卡在 76/76 时，模型又用全部 20 个队列槽请求
  Overlord，把人口上限直接推向 200。
- 根因：系统契约没有向模型解释“队列顺序只是优先级，不是 timing lock”，也没
  提供每个三族补给实体增加 8 人口、单轮通常只需 1-3 个的数量尺度。
- 修复：明确后项可能越过等待项，禁止把“几分钟后才想执行”的动作提前放入近期
  队列；同时给出补给增量、200 上限与 1-3 个近期开销边界。
- 自动化测试：prompt 合同覆盖 timing-lock 语义和补给数量边界。
- 初步 SC2 证据：加载新契约的 `optlurker734` 首轮只请求当前安全的
  Overlord/Drone/Hatchery/SpawningPool，不再包含远期 Extractor。
- 最新现象：`optlurker738` 已不再出现 20 Overlord，但个别周期仍会请求 4-5 个，
  且首轮仍把远期 Extractor 放入近期队列并被提前执行。按当前要求先记录为 context
  问题，不再用提示词调整抢占执行机制排查。
- Terran 同类证据：`optengine_t739` 在 observation 没有 Starport 时连续保留
  Medivac，并在 reason 中误称“continuing the Starport”。执行层正确地让 Medivac
  等待科技且未阻塞 Marine/Barracks 等后项；这是模型理解/策略上下文问题，统一
  留在本项，不用自动补科技的退化兜底掩盖。

### SC2-028：不同建筑同帧争用同一落点

- 日期：2026-07-30
- 状态：FIXED
- 现象：`optlurker734` 在 07:29 同帧为 LurkerDenMP 与 EvolutionChamber 都选择
  `(40.5, 116.5)`。两种 creation ability 各自只扫描同类型 worker order，
  因而看不见另一种建筑刚发出的重叠命令。
- 根因：`GridBuilding` 的在途位置检查按当前 unit type 隔离，而且 SC2 新命令要
  到下一 observation frame 才进入 worker.orders；不同 Act 实例没有共享本帧的
  建筑 footprint。
- 修复：所有 `GridBuilding` 按 `game_loop` 共享 `(position, half-size)` 预留；
  Terran 校验、Protoss 固定/动态落点、Zerg creep 落点都排除与本帧预留重叠的
  footprint，实际下单前立即预留，下一帧重置。
- 自动化测试：LurkerDenMP 预留后，EvolutionChamber 同点和部分重叠点均被拒绝，
  非重叠点可用，下一帧预留清空。
- 追加修复：Zerg 固定候选还会因只检查 creep/中心距离而反复下达无效命令；现已
  对每个候选调用 SC2 `can_place_single`，静态槽位耗尽后再围绕 ready Hatchery
  使用确定性的 `find_placement` 动态搜索。
- SC2 复测：`optlurker738` 同帧 HydraliskDen/EvolutionChamber 分别使用
  `(37.5,116.5)` 与 `(40.5,116.5)`，终局两者均真实存在；LurkerDenMP、
  InfestationPit 和后续 EvolutionChamber 也使用互不冲突的 footprint。

### SC2-029：多个扩张动作争用同一基地位置

- 日期：2026-07-30
- 状态：FIXED
- 现象：历史日志中多次出现两个 Expand 在不足一秒内选择同一坐标，例如
  `optp730` voidray 与 `optlurker732`；第一条 worker order 尚未进入下一帧时，
  第二个 Act 看见该 zone 仍可扩张。
- 根因：`Expand.expanding_in()` 只读取上一份 SC2 worker.orders，各 Act 没有共享
  “已经在本地发出、等待引擎确认”的 expansion zone。
- 修复：按坐标在 `ai` 上共享两秒确认窗口；发命令前预留，当前 Act 在窗口内不
  重发，兄弟 Act 会选择另一个合法 expansion；未确认则到期释放并允许真实重试。
- 自动化测试：确认两个 Expand 实例共享预留，当前 Act 不重发，并在确认窗口后
  自动释放。
- SC2 复测：`optengine_p738` 中两个连续扩张动作分别落在
  `(29.5,117.5)` 与 `(27.5,87.5)`，终局真实存在 3 座 Nexus；
  全场无重复 expansion 坐标、无 `NO_POS`、无 abandoned action。

### SC2-030：对不可取消结构发送 cancel

- 日期：2026-07-30
- 状态：FIXED
- 现象：`optlurker732/735` 中成长中的 CreepTumor 低血时连续多帧打印
  `Cancelled CREEPTUMOR`，但该引擎形态没有 `CANCEL_BUILDINPROGRESS` 能力。
- 根因：PlanCancelBuilding 仅凭 `0 < build_progress < 1` 推断可取消，未确认当前
  单位的 live available abilities。
- 修复：先批量查询 SC2 available abilities，仅对确实暴露
  `CANCEL_BUILDINPROGRESS` 的建筑发命令；不通过类型硬编码或吞异常冒充成功。
- 自动化测试：同一批候选中的 Barracks 有 cancel ability 因而收到命令，
  CreepTumor 没有该 ability 且不会收到命令。
- SC2 复测：加载修复后的 `optlurker738` 完整场中
  `Cancelled CREEPTUMOR=0`，其他错误/异常同样为 0。

### SC2-031：worker order 被误当作建筑已完成提交

- 日期：2026-07-30
- 状态：FIXED
- 现象：`optlurker735/736` 多次打印 `LURKERDENMP at ...` 后立即把 PA 标为 DONE，
  但 observation 中始终没有 LurkerDenMP；约一分钟后模型只好重新请求。类似问题
  会影响所有走 Sharpy GridBuilding/BuildGas/Expand 的建筑。
- 根因：`_build_action_satisfied()` 使用 `_build_progress_count()`，其中包含
  worker en-route order。worker order 只是意图，可能因工人死亡、碰撞或引擎拒绝
  消失，不能作为 scheduler 的不可撤销 commit boundary。
- 修复：只有 SC2 live unit cache 中出现真实 foundation（可未完工）才把建筑 PA
  标为 DONE；en-route order 仅保持 RUNNING 并阻止超时误杀，订单消失后原 Act
  会继续选工人和合法落点重试。
- 自动化测试：分别验证“1 条 en-route、0 foundation 不满足完成条件”以及
  “超时清理保持 RUNNING、绝不提前 DONE/ABANDON”。
- SC2 复测：`optlurker738` 的 LurkerDen PA 在 Drone order 后保持追踪，直到
  SC2 foundation 出现才 DONE；终局真实统计为 1 LurkerDenMP、4 LurkerMP，
  09:15 在至少 2 个 ready Lurker 后触发攻击，11:02 Victory。

### SC2-032：Terran direct-build 提前结束

- 日期：2026-07-30
- 状态：FIXED
- 现象：SupplyDepot/Barracks/Factory 等 Terran 直接建造路径只要看到 SCV
  携带目标 build order，就会清空 PA 预留并标为 DONE。若工人途中死亡、被控制
  或引擎拒绝落点，动作已经失去生命周期所有者，后续无法重选工人和落点。
- 根因：`DirectBuildExecutor` 将 `existing + en_route >= target` 作为提交完成；
  这与通用 GridBuilding 已修正的“真实 foundation 才算完成”边界不一致。
- 修复：en-route/fresh reservation 只保持 RUNNING 并阻止重复下单；只有 PA
  自己预留坐标上出现真实结构后才 DONE。订单消失超过确认窗口时仍按原机制释放
  无效位置并重试，没有吞掉任务或伪造成功。
- 跨决策周期修复：新模型队列只替换尚未提交的工作；已接受 worker order、但尚
  无 foundation 的 build PA 保留原 Act、预留与 worker handle，直到地基形成或
  订单消失后由同一个 PA 重试。普通 GridBuilding/BuildGas/Expand 在 Act 接受
  worker command 时也记录 committed copy，避免下一轮决策丢失生命周期所有者。
- 多建筑修复：Terran direct-build 的完成检查使用该 PA 自己预留坐标上的
  foundation 数量，不使用全局同类型建筑数；已有 6 座 Barracks 不会让第 7 座
  尚在赶路的 PA 被误判为满足。
- 自动化测试：覆盖 en-route 不 DONE、真实 foundation 才 DONE，以及超时检查
  保留 en-route 任务；另覆盖队列替换保留未落地建造、foundation 已存在时释放，
  以及旧同类建筑不能满足新 direct-build PA。
- SC2 复测：`optengine_t739`（Kimi-nothinking、Terran bio、Easy Zerg、
  AutomatonLE、10:00）中所有 DirectBuild `DONE` 均为
  `existing=1, en_route=0`。终局真实存在 10 SupplyDepot、7 Barracks、
  3 Bunker、1 Factory；同帧两座 Barracks/两座 SupplyDepot 均形成，
  unknown/unmapped/abandoned/NO_POS/error 均为 0。

### SC2-033：Expand/BuildGas 已发令却仍被当作未提交

- 日期：2026-07-30
- 状态：FIXED
- 现象：高频决策回归 `optengine_t740` 在 04:00 打印
  `Expanding to (35.5,34.5)` 并发送 CommandCenter build command；04:02 的新决策
  仍把 CommandCenter 列在 old uncommitted，模型省略后原 Expand Act 被替换。
- 根因：Expand/BuildGas 发出命令后按 Sharpy 协议返回 False（表示整体目标尚未完成），
  且没有 `GridBuilding.actual_placements`；Zerg Drone 开始 morph 后也不保证继续作为
  `ai.workers` build order 可见，scheduler 因此没有更新 committed copy。
- 修复：Expand/BuildGas 仅在实际调用 `worker.build*` 的帧暴露
  `issued_this_frame`。scheduler 同时使用该信号与 live
  `existing + worker build order`，记录 `issued_count` 并跨队列保留 Act；
  仍只在 live structure/foundation 达到 target 时 DONE。没有自动补建筑或伪造完成。
- 自动化测试：Expand 已有 1 基地、目标 2、live progress 仍为 1，但 Act 在本帧
  发出 worker command 时，PA 保持 RUNNING、`issued_count=1` 且带
  `awaiting foundation`。
- SC2 复测：`optengine_z745`（Kimi-nothinking、Zerg macro_roach、
  30 秒决策间隔）在 00:41 发出 Hatchery 扩张，随后仅在 SC2 出现真实 foundation
  时 DONE；01:00 observation 明确显示 Hatchery under construction，旧未提交列表
  为空，终局真实存在 2 座 Hatchery。unknown/unmapped/abandoned/NO_POS/error
  均为 0。最终最新代码的 `optengine_t741`、`optengine_p742`、
  `optengine_z745` 三族高频回归也均无 execution flag。

### SC2-034：分层 Prompt 中 canonical 名称与自动托管边界

- 日期：2026-07-30
- 状态：FIXED
- 环境：Easy Terran，KairosJunctionLE，15 个代表策略各 360 秒上限；
  `Kimi-k2.5` batch `promptv2_kimi_20260730`，
  `DeepSeek-V4-flash_think` batch `promptv2_deepseek_think_20260730`。
- 现象：两个模型共 247 次真实对局决策都能解析并执行，且无 traceback、
  decision exception、engine rejected、stuck abandon 或落点失败；但 DeepSeek
  有 3 次命名偏差：`InfantryWeaponsLevel1`、`CorvidReactor`，以及同一队列
  4 个 `WarpGate`。这些项被严格 catalog 丢弃，没有通过模糊别名兜底。
- 根因：
  1. `two_base_matrix_tanks/Top_agent.md` 使用旧的 `CorvidReactor`，而当前
     canonical 名是 `RavenCorvidReactor`。
  2. `four_gate/Top_agent.md` 要求“Convert ... to WarpGates”，与
     `MorphWarpGates` 自动托管边界冲突。
  3. 通用输出契约虽提供完整 canonical 列表，但没有要求返回前逐字复核，thinking
     模型仍会凭游戏记忆缩写升级名。
- 修复：
  1. Prompt 分成职责边界、决策生命周期、队列提交语义、种族机制、经济规则、
     策略目标、自动托管行为、观测字段说明、允许输出和 JSON 合约十部分。
  2. 每次用户消息明确提供 cycle、trigger、游戏时间、60 秒周期、敌方种族、
     fresh observation 和仅未提交队列；说明 queue-drained 最短 5 秒提前触发。
  3. 三族各自增加整体机制、优势、代价和宏观决策含义；说明 en route、active
     queues、ideal workers、army supply、power、enemy memory 和 completed
     research 等字段。
  4. 15 个策略各导出同源 `AUTOMATION_PROFILE`，真实战术构造和 prompt 共同
     使用其中攻击阈值；其余策略只保留目录并从 Registry/运行入口禁用。
  5. 修正 `RavenCorvidReactor` 与 four-gate 摘要，明确 WarpGate morph、
     Chrono、侦察、攻击、防御、微操和位置均由脚本托管；模型返回前必须把每个
     名称与可见 canonical 列表逐字比较。
- 自动化测试：`python -m pytest tools\tests -q` 为 75 passed；新增测试覆盖
  15 策略白名单、禁用策略拒绝、Profile 身份和 Profile 攻击阈值与真实
  `PlanZoneAttack.start_attack_power` 一致。
- 无引擎模型复测：修正后运行 `tools/probe_prompt_matrix.py`，Kimi 15/15、
  DeepSeek thinking 15/15 均为 parsed，unknown=0、unmapped=0、provider
  error=0。结果位于被 Git 忽略的
  `game_records/prompt_probes/promptv2_current_*.json`。
- SC2 复测：batch `promptv2_postfix_20260730`：
  DeepSeek `two_base_matrix_tanks`、DeepSeek `four_gate` 和 Kimi
  `twelve_pool` 各 180 秒，三场均 unknown=0、unmapped=0、interaction
  error=0、traceback=0；twelve-pool 按 power=3、阈值=2 正常触发自动攻击。
- 跨模型/种族结果：原 30 场短局全部首次生成有效记录；Kimi 的 marine-rush、
  four-gate、dark-templar、voidray、twelve-pool，以及 DeepSeek 的
  marine-rush、four-gate、robo、voidray、twelve-pool 均出现真实
  `Attack started`。高阈值或附加门槛策略在 360 秒内未进攻符合配置，不应通过
  降低阈值伪造覆盖。

## 新异常模板

复制以下内容追加到文件末尾，并同时更新顶部索引：

```markdown
### SC2-NNN：简短标题

- 日期：
- 状态：OPEN
- 环境：分支、提交、地图、我方种族/策略、敌方种族/难度、模型、时间上限
- 复现命令：
- 预期：
- 实际：
- 日志/JSON/Replay 证据：
- 根因：
- 修复文件：
- 自动化测试：
- SC2 复测：
- 跨种族回归：
- 备注：
```
