# V2 knowledge / no-external-knowledge 轨迹对照方案

## 1. 研究问题

核心问题不是“知识是否正确”，而是：在 V2 harness 已经提供强规划约束的前提下，
DataSubAgent 外部检索是否让 MainAgent 在相同状态下做出更及时、可执行且能赢得比赛的
决策；如果没有，损失发生在检索触发、结果表达、知识整合、队列执行还是后续反馈阶段。

## 2. 建立严格的配对清单

每个样本必须按以下字段配对，任一关键字段不一致就标记为 confounded，不得直接做因果
比较：

- 我方种族、敌方种族、策略、地图、难度、敌方风格；
- MainAgent / DataSubAgent provider、模型和 reasoning 实际状态；
- 决策间隔、最大时长、并发设置；
- V2 prompt、harness、数据集和代码 commit；
- run index，以及可获得时的 SC2 seed。

reasoning 状态以调用 trace 中的 `reasoning_requested`、实际 `model_key`、
`is_reasoning` 和 `reasoning_source` 为准，不能以 batch 名或 `_think` 配置名为准。
2026-08-04 no-external-knowledge batch 里只有带 `match.json` 的后六个目录是完整对局；
前六个中断目录只能用于诊断启动/调用问题。

当前待审阅的探索性配对如下。它们的 matchup/run index 对齐，但由于 harness 修订号与
seed/commit 记录不完整，统一标记为“有混杂，仅供探索”：

| Pair | knowledge run | no-external-knowledge run |
|---:|---|---|
| 0 | `20260803_234402_t_p_yamato_run0` | `20260804_125255_t_p_yamato_run0` |
| 1 | `20260803_234402_t_z_yamato_run1` | `20260804_125255_t_z_yamato_run1` |
| 2 | `20260803_234402_p_t_darktemplar_run2` | `20260804_125255_p_t_darktemplar_run2` |
| 3 | `20260803_234402_p_z_darktemplar_run3` | `20260804_125256_p_z_darktemplar_run3` |
| 4 | `20260803_234402_z_t_lurkers_run4` | `20260804_125307_z_t_lurkers_run4` |
| 5 | `20260803_234402_z_p_lurkers_run5` | `20260804_125309_z_p_lurkers_run5` |

## 3. 分配给轨迹分析 Agent 的任务

每个 Agent 领取一个 matchup 对，按 [`TRACE_REVIEW_TEMPLATE.md`](TRACE_REVIEW_TEMPLATE.md)
产出报告。必须同时阅读 knowledge 和 control 两条轨迹，禁止只解释失败方。

1. 从 `match.json` 建立结果、时长和宏观指标摘要。
2. 从 `match.llm_calls.json` 对齐相近游戏时间的 observation、planning snapshot、
   query、公开 decision reason、ordered queue 和 queue audit。
3. 对 knowledge 轨迹中的每次外部查询建立 query ledger：为什么查、查了什么、返回什么、
   下一队列用了什么、游戏内是否在合理时间窗内执行。
4. 找到两条轨迹第一次产生实质差异的决策，而不是从终局倒推单一原因。
5. 沿后续 2 至 4 个决策周期追踪差异是否扩大、被修复或与胜负无关。
6. 给出最小反事实：如果保留相同 observation 和 harness，只移除该次外部结果，最可能
   保留/改变哪些队列项。无法从证据判断时必须写“不确定”。

不要让 Agent 复述长 prompt 或隐藏 chain-of-thought。报告只引用可审计字段，并为关键
证据写明 batch、run 目录、game time 和 JSON 字段路径。

## 4. 每次查询的归因标签

每次查询只能选择一个主标签，可附一个次标签：

- `beneficial_actionable`：正确、当前相关，并及时改变了可执行动作；
- `correct_unused`：答案正确，但没有进入队列或后续动作；
- `redundant`：harness、observation 或模型先验已经足够，检索没有新增决策信息；
- `harmful_anchor`：答案促使决策过度围绕某实体/克制关系，挤掉更高优先级动作；
- `incomplete_context`：静态事实正确，但缺少规模、时机、地图、生产容量或升级等条件；
- `stale`：从 observation 到决定/执行时状态已经变化；
- `incorrect_or_misaligned`：实体、版本、关系方向、目标层或可用性存在错误；
- `causally_indeterminate`：现有记录不足以判断。

“knowledge_application” 是模型自报字段，只能作为线索。只有当返回事实、决策差异和
后续执行三者形成证据链时，才能认定知识产生了作用。

## 5. 统一指标

除胜/平/负外，每对轨迹至少比较：

- 资源：RUR、平均浮动资源、矿/气收入与库存、工人数、基地数；
- 战力：APU、army supply、可攻击空中/地面的覆盖、关键升级与主力构成；
- 计划质量：预算覆盖率、战力缺口、supply 余量、生产容量、先决条件违规；
- 稳定性：队列 churn、carried/discarded 项、repair/fallback 次数；
- 检索：查询数、round 数、cache 命中、工具返回规模、从查询到执行的时间；
- 时序：首次分叉点、关键接战、扩张/科技窗口和终局时间。

## 6. 汇总规则

先做逐对结论，再跨 matchup 汇总。不得用六局直接估计稳定胜率。最终汇总需要区分：

- harness 自身带来的收益；
- 外部检索的边际收益或损失；
- 模型/推理开关、代码版本、并发或随机性造成的混杂。

只有在同一 commit、同一配置、有效 reasoning 审计且完成重复种子的配对实验后，才把
差异表述为 knowledge 的因果效应。
