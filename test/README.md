# V2 测试与轨迹分析

`test/` 当前只维护 V2 harness 的评测方法、轨迹归因和后续实验设计。2026 年
7 月以前用于朴素 Agent、V1 和早期回归矩阵的材料已经冻结在
[`archive/2026-07-legacy-agent-validation/`](archive/2026-07-legacy-agent-validation/README.md)，
不再作为当前测试入口。

## 当前发现

V2 在规划快照、资源/战力转换审计、执行容量约束和队列稳定化等 harness
加持下表现很好。不过，2026-08-04 的探索性六对局对照出现了明确的反常信号：

| 条件 | 完整对局 | 胜 | 平 | 负 |
|---|---:|---:|---:|---:|
| V2 + 外部 DataSubAgent knowledge | 6 | 2 | 4 | 0 |
| V2 + no-external-knowledge control | 6 | 6 | 0 | 0 |

对应记录：

- knowledge：`game_records/v2_ds4f_mh_3race_20260804_harness_r2/`
- no-external-knowledge：`game_records/v2_no_knowledge_ds4f_mh_3race_20260804_r5/`

这里的 “no-external-knowledge” 只表示关闭 DataSubAgent 的外部检索能力；V2
harness 本身仍保留规划器、审计器和模型已有知识。因此该对照测量的是“外部检索的
边际作用”，不是“完全有知识”与“完全无知识”。

这个结果目前是需要解释的强信号，不是最终因果结论：样本只有六个 matchup，两个
batch 名还表明 harness 修订号不同，且 no-external-knowledge 目录中另有六个没有
`match.json` 的中断尝试。中断尝试不得计入胜率或当作独立样本。

## 当前工作入口

- [`V2_3_VALIDATION_REPORT.md`](V2_3_VALIDATION_REPORT.md)：V2.3 通用文本调用、
  Hard 20 分钟基线、知识负迁移归因，以及按空中/地面威胁拆分的组合式修正。
- [`V2_KNOWLEDGE_ABLATION_PLAN.md`](V2_KNOWLEDGE_ABLATION_PLAN.md)：如何严格配对
  knowledge / no-external-knowledge 轨迹，以及交给其他 Agent 的分析任务。
- [`TRACE_REVIEW_TEMPLATE.md`](TRACE_REVIEW_TEMPLATE.md)：每个 matchup 的统一审阅模板。
- [`KNOWLEDGE_NEGATIVE_TRANSFER_ANALYSIS.md`](KNOWLEDGE_NEGATIVE_TRANSFER_ANALYSIS.md)：
  当前可检验的负迁移假设、已有证据和下一步实验优先级。

分析时以 `match.json`、`match.llm_calls.json` 和相应 trace JSON 为事实来源。不要用
batch 名推断 reasoning 是否开启，也不要引用模型的隐藏思维过程；只使用 observation、
结构化规划字段、工具请求/返回、公开 decision reason、最终队列和比赛结果。
