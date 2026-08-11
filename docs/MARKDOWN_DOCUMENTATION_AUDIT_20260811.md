# Markdown 文档审计记录（2026-08-11）

## 范围

本次审计覆盖 outer repo 与 Agent submodule 中所有已跟踪 `*.md`。操作性文档、
README、实验配置和事故记录逐项更新；vendored knowledge、单位资料、策略输入、
测试 fixture、生成的 Skill/节点以及历史归档只检查是否会误导当前启动流程，不
机械改写其领域内容或实验产物。

## 发现与处理

1. 两份 SC2 observation 事故文档重复。保留精简最终根因文档，将长时间线移入
   `docs/archive/` 并标明其中的中间结论不再代表当前状态。
2. 启动约束散落于 runtime、environment、workflow、architecture 和 tools README。
   新增 `SC2_BATCH_EXPERIMENT_POLICY.md` 作为唯一现行规范，其余文档只引用它。
3. outer README 仍引用已替换的 `SC2-Agent-knowlegde` submodule 名称和旧分支，
   已更新为 `SC2-Agent-human-skill` / `codex/human-skill-agent`。
4. 完成计划归档仍写“持续排查”，已更新为最终根因和 15/15 验收状态。

## 不机械更新的内容

- `SC2_Agent/knowledge_*`：vendored knowledge；
- `SKILL/**/Top_agent.md`：版本化策略输入；
- `tools/tests/fixtures/**`：schema/loader 回归 fixture；
- outer `SKILL_MINING_V2*` 与 Readable node Markdown：实验产物；
- `test/archive/**` 与 outer `archive/pre_v2/**`：历史证据。

修改这些文件会改变知识、fixture 或实验输出本身，不属于文档去重任务。
