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
| SC2-011 | 2026-07-30 | OPEN | 批量工具 | strategy sweep 未传递 bot-race，只适合当前默认种族 |

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

- 现象：`tools/run_kimi_nothink_strategy_sweep.py` 调用
  `tools/run_experiment.py` 时没有传递 `--bot-race`。
- 风险：用该 sweep 测 Protoss/Zerg 策略时会使用 `run_experiment.py` 的默认
  Terran，从而产生无效结果。
- 当前规避：新增种族测试必须直接调用 `run_experiment.py --bot-race ...`，并且
  串行启动本地 SC2。
- 后续修复建议：给 sweep 增加 `--bot-races` 矩阵字段，把我方种族纳入
  `MatchJob`、match id、完成判断和命令参数，然后补 dry-run 测试。

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
