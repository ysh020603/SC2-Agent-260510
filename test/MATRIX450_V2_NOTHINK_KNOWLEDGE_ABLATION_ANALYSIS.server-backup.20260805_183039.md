# Matrix450：V2 nothink knowledge vs no-knowledge 轨迹深挖

- 分析日期：2026-08-05
- 范围：`matrix450_qwen3_32b_v2_nothink_20260804` vs `matrix450_qwen3_32b_v2_noknowledge_nothink_20260804`
- 方法依据：[`README.md`](README.md)、[`V2_KNOWLEDGE_ABLATION_PLAN.md`](V2_KNOWLEDGE_ABLATION_PLAN.md)、[`TRACE_REVIEW_TEMPLATE.md`](TRACE_REVIEW_TEMPLATE.md)、[`KNOWLEDGE_NEGATIVE_TRANSFER_ANALYSIS.md`](KNOWLEDGE_NEGATIVE_TRANSFER_ANALYSIS.md)
- 本文件只记录只读分析结果与证据路径，不包含代码改动

## 0. 一句话结论

两边 450 局可按 `run0–449` 严格配对；knowledge 胜率显著更低（20.9% vs 35.8%）。  
**主因不是知识内容负迁移，而是 Knowledge 侧 DataSubAgent 工具调用 100% 失败**（vLLM 400：`auto` tool choice 未启用），失败决策写入空 `ordered_names`，导致生产停摆、资源空转。

未触发 SubAgent 的 66 局里，knowledge 胜率反为 **92.4%**（对照 81.8%），说明同一 harness/模型在“不走坏掉的工具路径”时并不差。

---

## 1. 实验身份与数据位置

| 项 | V2 knowledge nothink | V2 no-knowledge nothink |
|---|---|---|
| batch | `matrix450_qwen3_32b_v2_nothink_20260804` | `matrix450_qwen3_32b_v2_noknowledge_nothink_20260804` |
| mode | `data-v2.2-v2` | `data-v2.2-v2-no-knowledge` |
| 结果根目录 | `game_records/matrix450_qwen3_32b_v2_nothink_20260804/` | `game_records/matrix450_qwen3_32b_v2_noknowledge_nothink_20260804/` |
| 轨迹目录名 | `kv2_traces/<date>/<run_id>/trace.json` | `kv2_no_knowledge_traces/<date>/<run_id>/trace.json` |
| 单局记录 | `match.json` / `match.llm_calls.json` / `match.log` / `match.SC2Replay` | 同左 |
| 模型证据 | `model_key=qwen3-32b`，`is_reasoning∈{false,null}`，`reasoning_source=none` | 同左 |
| agent_version（llm_calls） | `decision-data-v2.2-v2` | `decision-data-v2.2-v2-no-knowledge` |
| dataset | `SC2_Agent/knowledge_v2_2_v2/data_sc2_260701/data_base_sc2_260701.json` | 同左（N 侧 `knowledge_database_access=false`） |

模式说明文档：

- `docs/data-v2.2-v2-decision-agent.md`
- `docs/data-v2.2-v2-no-knowledge.md`

已知混杂（不影响本文件主结论，但限制“知识内容因果”表述）：

- 并发：knowledge≈10，no-knowledge≈5
- 启动方式不同（parallel sweep vs config suite）
- 难度字段在目录名中只有 `ea/me/ha` 三档（各 90/180/180），不是五档

---

## 2. 配对清单规则

配对键：目录名中的 `runN`（`run0`…`run449`）。

对全部 450 对检查以下字段，**0 处不一致**：

`bot_race / strategy / enemy_race / difficulty / repeat / matchup`

因此可做逐对胜负与宏观指标对照。  
但对“外部知识内容是否有害”的因果表述，必须降级：knowledge 侧 **没有任何一次成功的 tool_result / sub_direct_answer**。

配对有效性标签：

- 对局结果与执行层故障：**严格配对，可比较**
- 知识内容边际效应：**不可从本 batch 直接估计**（检索通路未接通）

---

## 3. 总体结果

### 3.1 胜负

| 条件 | Victory | Tie | Defeat | 胜率 |
|---|---:|---:|---:|---:|
| knowledge | 94 | 32 | 324 | **20.9%** |
| no-knowledge | 161 | 85 | 204 | **35.8%** |

以 Victory 计的配对交叉：

| | N Victory | N 非 Victory |
|---|---:|---:|
| K Victory | 76 | 18 |
| K 非 Victory | 85 | 271 |

完整结果交叉（K×N）：

| K \ N | Victory | Tie | Defeat |
|---|---:|---:|---:|
| Victory | 76 | 4 | 14 |
| Tie | 10 | 20 | 2 |
| Defeat | 75 | 61 | 188 |

### 3.2 宏观指标（450 对均值）

| 指标 | knowledge | no-knowledge | 说明 |
|---|---:|---:|---|
| RUR（消耗/分） | 438.7 | **748.3** | 越高越好 |
| 平均浮动资源 | **2400.8** | 1778.0 | 越高越差 |
| APU | 0.587 | 0.622 | 越高越好 |
| 对局时长 (s) | 746 | 846 | |
| 决策记录数 | 12.3 | 13.9 | |
| llm calls | 18.2 | 22.7 | |
| 空队列决策占比 | **35.3%** | 6.5% | `ordered_names=[]` |
| 末尾连续 ≥3 次空队列的对局数 | **329** | 79 | |

### 3.3 分层：matchup

| matchup | K 胜率 | N 胜率 | Δ |
|---|---:|---:|---:|
| PvP | 36.0% | 50.0% | +14 |
| PvT | 22.0% | 32.0% | +10 |
| **PvZ** | **0.0%** | **48.0%** | **+48** |
| TvP | 34.0% | 38.0% | +4 |
| TvT | 24.0% | 30.0% | +6 |
| **TvZ** | **10.0%** | **36.0%** | **+26** |
| ZvP | 26.0% | 30.0% | +4 |
| ZvT | 22.0% | 32.0% | +10 |
| ZvZ | 14.0% | 26.0% | +12 |

PvZ 的 50 对交叉：K 无胜利；其中 `K=Defeat & N=Victory` 23 局。

### 3.4 分层：难度

| 难度 | n | K 胜率 | N 胜率 |
|---|---:|---:|---:|
| easy | 90 | 44.4% | **75.6%**（N 在 easy 0 败） |
| medium | 180 | 20.6% | 35.6% |
| harder | 180 | 9.4% | 16.1% |

### 3.5 分层：策略（每策略 30 局）

差距最大的策略（N−K 胜率）：

- `macrostalk` +33%、`robo` +30%、`mutalisk` +23%、`voidray/yamatorust/darktempla/blueflamel` +20%

几乎不受影响 / 两边都强：

- `twelvepool`：K 83% / N 93%；其中 **20/30 局 K 未触发 Sub，且这 20 局全胜**

两边都弱：

- `lurkers`、`twobasemat`、`macroroach`

---

## 4. 检索 / SubAgent 审计（全量）

### 4.1 Knowledge 侧事件总量（7722 个 decision traces）

| 事件 | 次数 |
|---|---:|
| `sub_session_started` | 2498 |
| `sub_tool_selection` | 2498 |
| `llm_error` | **2498** |
| `sub_tool_selection_fallback` | 1329 |
| `sub_direct_answer` | **0** |
| `tool_result` / `sub_tool_result` | **0** |
| `status=failed` 的 trace | **2498** |

触发 SubAgent 的对局：384 / 450。  
错误信息 **全部相同**：

```text
completion_failed: Error code: 400 - {"object":"error","message":"\"auto\" tool choice requires --enable-auto-tool-choice and --tool-call-parser to be set","type":"BadRequestError","code":400}
```

失败查询类型（有 `ask_subagent` 记录的）：

| query_type | 次数 |
|---|---:|
| `enemy_counter` | 1401 |
| `resource_facts` | 13 |
| `combat_capability` | 5 |
| `tech_feasibility` | 3 |

失败目标 Top：`ZERGLING`(811)、`MARINE`(274)、`STALKER`(173)、`ROACH`(129)、`ADEPT`(109)。  
失败时刻中位游戏时间约 **533s**（均值 ~538s）；但大量 vsZ 局在 **150–180s** 首次失败。

### 4.2 No-knowledge 侧

| 事件 | 次数 |
|---|---:|
| `sub_session_started` | 1088 |
| `sub_direct_answer` | 1088 |
| `llm_error` | 1（超时） |
| `answer_source=model_prior` | 1826（含汇总计数） |
| `answer_source=model_prior_cache` | 795 |
| `knowledge_database_access` | 恒为 false |

N 侧 Sub 能返回；Main 可继续给出非空队列。prior 内容可以错误（例如把 Baneling 当作神族/人族对策），但**不会像 K 那样整轮决策崩溃**。

### 4.3 与胜率的相关性（几乎决定性）

| 子集 | n | K 胜率 | 同批 N 胜率 |
|---|---:|---:|---:|
| K 触发 Sub（必失败） | 384 | **8.6%** | 27.9% |
| K 未触发 Sub | 66 | **92.4%** | 81.8% |
| K 从未出现空队列 | 56 | **96.4%** | — |
| K 首次空队列 &lt;300s | 166 | 6.0% | — |
| K 空队列占比 ≥50% | 140 | **0%** | — |

在 384 局“K 触发 Sub”的配对中：仅 N 胜 84，仅 K 胜 10。

`first_fail` 与 `first_empty` 在 ±5s 内对齐：**359 / 384**。  
说明主导模式是：**工具失败 → 该决策 `ordered_names=[]`**。  
少数“空队列早于 first_fail”的局（如 run251 在 88s 主动空队列）存在，但不改变主因果链。

`match.llm_calls.json` 中失败后的 call 常表现为 `is_reasoning=null` 且 `ordered_names=[]`。

---

## 5. 失败链路（可复现）

Knowledge 单次决策的典型事件序：

1. `main_decision` round0：`final_decision`，往往已有合理队列（如 10×Marine / Gateway）
2. `main_decision` round1：`ask_subagent`（多为 `enemy_counter`）
3. `sub_session_started`
4. `sub_tool_selection`（选出 `query_counter_relations` 等）
5. `llm_error`（tool_choice=auto 400）
6. `run_finished` `status=failed`，`result={}`
7. 对应 `match.llm_calls.json` 写入空队列

这与 [`KNOWLEDGE_NEGATIVE_TRANSFER_ANALYSIS.md`](KNOWLEDGE_NEGATIVE_TRANSFER_ANALYSIS.md) 中“答案正确但未进入队列 / 克制锚定”等**内容级**假设不同：本 batch 中外部答案根本没有返回。

建议的归因标签（相对原模板）：

- 主标签：`infrastructure_tool_failure`（检索路径运行时失败）
- 后果标签：`decision_abort_empty_queue`
- 不宜使用：`beneficial_actionable` / `harmful_anchor` / `incorrect_or_misaligned`（缺少返回事实）

---

## 6. 配对轨迹审阅

路径均相对于 `game_records/`。

### 6.1 Pair run250 — PvZ fourgate · easy · r1

| 项 | knowledge | no-knowledge |
|---|---|---|
| 目录 | `matrix450_qwen3_32b_v2_nothink_20260804/20260804_083626_p_fourgate_Kairos_zea_r1_run250/` | `matrix450_qwen3_32b_v2_noknowledge_nothink_20260804/20260805_005528_p_fourgate_Kairos_zea_r1_run250/` |
| 结果 | Defeat 747.3s | Victory 463.0s |
| RUR / float / APU | 158.6 / 3841.1 / 0.692 | 631.8 / 650.1 / 0.721 |
| Sub | 10 次，全失败 | model_prior 可返回 |

**首次实质分叉（K）**

- 游戏时间：约 **171.4s**
- 证据 trace：  
  `matrix450_qwen3_32b_v2_nothink_20260804/20260804_083626_p_fourgate_Kairos_zea_r1_run250/kv2_traces/2026-08-04/003809_96ad03ff6f3a/trace.json`
- round0 已规划生存队列（摘要称要产 Zealot/Stalker；该 round 的 `ordered_names` 记录为 8×`GATEWAY`）
- round1：`ask_subagent` / `enemy_counter` / targets=`ZERGLING`
- 工具选择：`query_counter_relations`, `query_combat_capabilities`, `query_candidate_plan_facts`
- 随即 400 错误，`run_finished.status=failed`
- `match.llm_calls.json`：`game_time=171.43` 起连续空队列（`is_reasoning=null`）

**对照（N）**

- 证据 trace：  
  `matrix450_qwen3_32b_v2_noknowledge_nothink_20260804/20260805_005528_p_fourgate_Kairos_zea_r1_run250/kv2_no_knowledge_traces/2026-08-04/165639_1a3cd208a993/trace.json`
- ~155.8s 同类 `enemy_counter(ZERGLING)`
- `sub_direct_answer.answer_source=model_prior`，实体含 `ZEALOT/STALKER/...`
- round2 最终队列：`['Stalker']`，对局继续并取胜

**差异传播**

- K：171s 后多数决策空队列 → 浮动资源飙升、几乎无战力转化 → 747s 败北
- N：持续 Zealot/Probe 生产，463s 胜利

**最小反事实**

- 若 Sub 失败时回退到 round0 已有队列，或工具通路可用，K 极可能避免从 ~3 分钟起的生产停摆。  
- 无法从本对局证明“ZEALOT 知识本身有害”。

### 6.2 Pair run100 — TvZ marinerush · easy · r1

| 项 | knowledge | no-knowledge |
|---|---|---|
| 目录 | `.../20260804_061706_t_marinerush_Kairos_zea_r1_run100/` | `.../20260804_183709_t_marinerush_Kairos_zea_r1_run100/` |
| 结果 | Defeat 829s | Victory 412s |
| RUR / float / APU | 211.8 / 3124.5 / 0.460 | 749.9 / 64.2 / 0.581 |

**K 首次失败**

- 时间：约 **149.6s**
- trace：  
  `matrix450_qwen3_32b_v2_nothink_20260804/20260804_061706_t_marinerush_Kairos_zea_r1_run100/kv2_traces/2026-08-03/221831_d16030f12d5f/trace.json`
- round0：已提出 `10×MARINE`（生存优先级，针对 Roach/Zergling）
- round1：仍去查 `enemy_counter(ZERGLING)`“验证 Marine 是否为 counter”
- 工具 400 → 失败；`match.llm_calls.json` 在 `149.55` 记空队列

**N 对照**

- trace：  
  `matrix450_qwen3_32b_v2_noknowledge_nothink_20260804/20260804_183709_t_marinerush_Kairos_zea_r1_run100/kv2_no_knowledge_traces/2026-08-04/103839_1f5ae8d16997/trace.json`
- prior 回答：Marine/Ghost/Banshee 可打 Zergling
- 最终队列：`7×MARINE + SUPPLYDEPOT`，412s 胜利

**机制解读**

- Main 在查询前已经有可执行的 Marine 队列；失败把“验证性查询”变成了“整轮决策作废”。  
- 标签：`infrastructure_tool_failure` + 可能的次要问题 `query_not_aligned_with_gap`（缺口已是产能执行，不是静态事实）。

### 6.3 Pair run0 — TvT marinerush · easy · r1（阴性对照）

| 项 | knowledge | no-knowledge |
|---|---|---|
| 目录 | `.../20260804_043915_t_marinerush_Kairos_tea_r1_run0/` | `.../20260804_143058_t_marinerush_Kairos_tea_r1_run0/` |
| 结果 | **Victory 403s** | Victory 549s |
| RUR / float / APU | 804.6 / 62.5 / 0.625 | 716.3 / 223.7 / 0.515 |
| K Sub | **0**（无失败） | 有 model_prior（~268.8s） |

K 全程非空队列、稳定 Marine 洪水。  
说明：**同一矩阵单元上，knowledge 模式在不触发坏工具路径时可以不弱于 control。**

N 的 prior 甚至出现跨种族噪声（Medivac/Baneling/Widow Mine/Thor 混谈），但未阻止取胜。

N 首次 Sub trace：  
`matrix450_qwen3_32b_v2_noknowledge_nothink_20260804/20260804_143058_t_marinerush_Kairos_tea_r1_run0/kv2_no_knowledge_traces/2026-08-04/063449_6fad4931d75f/trace.json`

### 6.4 Pair run8 — TvT twobasemat · easy · r2（K 更好的少见例）

| 项 | knowledge | no-knowledge |
|---|---|---|
| 目录 | `.../20260804_043931_t_twobasemat_Kairos_tea_r2_run8/` | `.../20260804_144002_t_twobasemat_Kairos_tea_r2_run8/` |
| 结果 | Victory 854s | Tie 1200s |
| K Sub | 0 | ~900s prior（含 Baneling/Gorge 等噪声） |

支持：N 的 prior 质量不保证；但 **空队列崩溃比错误 prior 更致命**。

N Sub trace：  
`matrix450_qwen3_32b_v2_noknowledge_nothink_20260804/20260804_144002_t_twobasemat_Kairos_tea_r2_run8/kv2_no_knowledge_traces/2026-08-04/064922_a0fb291e959d/trace.json`

### 6.5 补充：PvZ “K 非胜且 N 胜”样本头 10 局

这些局普遍在 ~140–180s 首次 `enemy_counter(ZERGLING)` 失败：

| run | strategy | diff | K first_fail | K first_empty | K 目录后缀 |
|---:|---|---|---:|---:|---|
| 250 | fourgate | ea | 171.4 | 171.43 | `..._p_fourgate_Kairos_zea_r1_run250` |
| 251 | darktempla | ea | 148.7 | 88.39* | `..._p_darktempla_Kairos_zea_r1_run251` |
| 252 | robo | ea | 175.9 | 175.89 | `..._p_robo_Kairos_zea_r1_run252` |
| 253 | voidray | ea | 155.4 | 155.36 | `..._p_voidray_Kairos_zea_r1_run253` |
| 255 | fourgate | ea | 163.4 | 163.39 | `..._p_fourgate_Kairos_zea_r1_run255` |
| 256 | darktempla | ea | 146.0 | 145.98 | `..._p_darktempla_Kairos_zea_r1_run256` |
| 257 | robo | ea | 167.9 | 167.86 | `..._p_robo_Kairos_zea_r1_run257` |
| 258 | voidray | ea | 196.4 | 136.16* | `..._p_voidray_Kairos_zea_r1_run258` |
| 259 | macrostalk | ea | 142.9 | 142.86 | `..._p_macrostalk_Kairos_zea_r1_run259` |
| 262 | robo | me | 164.7 | 164.73 | `..._p_robo_Kairos_zeme_r1_run262` |

\* run251/258：存在“主动空队列”早于首次工具失败；其后仍进入反复失败模式。  
run251 在 `88.4s` 的 trace 为 `status=completed` 且无 `ask_subagent`，说明空队列不全由工具失败造成，但 **148.7s 起进入失败循环**。

---

## 7. Query ledger（展示对，按模板）

### run250 knowledge

| 时间 | 不确定性 | 返回事实 | 队列变化 | 后续执行 | 主标签 | 证据 |
|---|---|---|---|---|---|---|
| 171.4s | Zergling counter | **无（400）** | 计划中的生存队列 → 空 | 否 | infrastructure_tool_failure | `.../003809_96ad03ff6f3a/trace.json` + `match.llm_calls.json@171.43` |
| 231.7s | 同上 | 无 | 空 | 否 | 同上 | 同目录后续 failed traces |
| …共 10 次 | 多为 ZERGLING | 无 | 持续空 | 否 | 同上 | `kv2_traces/2026-08-04/*/trace.json` |

### run250 no-knowledge

| 时间 | 不确定性 | 返回事实 | 队列变化 | 后续执行 | 主标签 | 证据 |
|---|---|---|---|---|---|---|
| 155.8s | Zergling counter | model_prior：Zealot/Stalker 等 | 维持/确认 Stalker | 是（对局继续） | beneficial_actionable（弱：多为确认先验） | `.../165639_1a3cd208a993/trace.json` |
| 275.9s | Roach counter | model_prior：Zealot/Sentry/Phoenix | Probe+Zealot | 是 | redundant / incomplete_context（混有 Phoenix） | 同 run 后续 sub traces |

### run100 knowledge / no-knowledge

| 侧 | 时间 | 结果 | 标签 | 证据 |
|---|---|---|---|---|
| K | 149.6s | 10×Marine 草稿 → 空 | infrastructure_tool_failure | `.../221831_d16030f12d5f/trace.json` |
| N | 140.6s | prior 确认 Marine → `7×Marine+Depot` | beneficial_actionable（策略内确认） | `.../103839_1f5ae8d16997/trace.json` |

---

## 8. 对既有负迁移假设的修订

对照 [`KNOWLEDGE_NEGATIVE_TRANSFER_ANALYSIS.md`](KNOWLEDGE_NEGATIVE_TRANSFER_ANALYSIS.md)：

| 原假设 | 本 450 局 nothink 矩阵中的地位 |
|---|---|
| 强 harness 已覆盖大部分价值 | 仍可能成立，但被工具故障掩盖；未触发 Sub 时 K 很强 |
| 静态克制锚定挤掉更高优先级动作 | **未能检验**（无成功返回） |
| 查询与缺口不对齐 | 有线索（run100 已有 Marine 仍去验证），但是**次要**于失败中止 |
| 结果过宽导致策略漂移 | **未能检验** |
| 知识使用自报不可信 | 仍然成立；且本 batch 更应忽略 `knowledge_application` |
| 更多 Agent round 增加 churn | K 失败 run 直接中止，表现为空队列而非“多 round 修复” |

**当前最可能机制（本矩阵）**

1. SubAgent tool calling 与推理服务配置不兼容（主因，已证实）
2. 失败无回退 → 空队列写入（直接伤害）
3. vsZ 更早侦察到 Zergling，更早触发 `enemy_counter`，故 PvZ/TvZ 崩盘最重（触发率放大主因）
4. 内容级负迁移：需工具修复后重测

---

## 9. 如何复核单条证据

对任意 `runR`：

1. 在两边目录中找到 `*_runR`
2. 读 `match.json` → `metadata.result` / `macro_metrics`
3. 读 `match.llm_calls.json` → 逐 call 的 `ordered_names`、`is_reasoning`、`decision_agent_mode`、`model_key`
4. Knowledge：扫 `kv2_traces/*/*/trace.json`，过滤 `type==llm_error` 或 `status==failed`
5. No-knowledge：扫 `kv2_no_knowledge_traces/*/*/trace.json`，查找 `sub_direct_answer.answer_source`

快速统计口诀：

- `sub_session_started` 次数是否等于 `llm_error` 次数（K 侧应为相等）
- 空队列 call 的 `game_time` 是否贴着首次 `llm_error` 的 Game time

---

## 10. 建议的下一步（未实施）

1. **修复服务端工具调用**：为 qwen3-32b 推理服务启用 `--enable-auto-tool-choice` 与匹配的 `--tool-call-parser`；或改客户端 `tool_choice` 策略。
2. **决策层回退**：Sub 失败时回退到 `ask_subagent` 前最后一次合法 `final_decision` 队列；禁止把失败 run 记成空队列。
3. **门禁指标**：batch 健康检查应要求 `llm_error(sub_*)==0` 且 `sub_direct_answer`/`tool_result` 成功率高于阈值，否则不进入胜率比较。
4. **再跑同矩阵**后，才按原模板重做内容级负迁移（`redundant` / `harmful_anchor` / `correct_unused` 等）。
5. 修复前，不要把本 450 局的胜率差解释为“外部知识有害”。

---

## 11. 相关文件索引

方法与模板：

- `test/README.md`
- `test/V2_KNOWLEDGE_ABLATION_PLAN.md`
- `test/TRACE_REVIEW_TEMPLATE.md`
- `test/KNOWLEDGE_NEGATIVE_TRANSFER_ANALYSIS.md`

数据根：

- `game_records/matrix450_qwen3_32b_v2_nothink_20260804/`
- `game_records/matrix450_qwen3_32b_v2_noknowledge_nothink_20260804/`

本分析重点 trace（复制路径便于跳转）：

```text
game_records/matrix450_qwen3_32b_v2_nothink_20260804/20260804_083626_p_fourgate_Kairos_zea_r1_run250/kv2_traces/2026-08-04/003809_96ad03ff6f3a/trace.json
game_records/matrix450_qwen3_32b_v2_noknowledge_nothink_20260804/20260805_005528_p_fourgate_Kairos_zea_r1_run250/kv2_no_knowledge_traces/2026-08-04/165639_1a3cd208a993/trace.json
game_records/matrix450_qwen3_32b_v2_nothink_20260804/20260804_061706_t_marinerush_Kairos_zea_r1_run100/kv2_traces/2026-08-03/221831_d16030f12d5f/trace.json
game_records/matrix450_qwen3_32b_v2_noknowledge_nothink_20260804/20260804_183709_t_marinerush_Kairos_zea_r1_run100/kv2_no_knowledge_traces/2026-08-04/103839_1f5ae8d16997/trace.json
game_records/matrix450_qwen3_32b_v2_nothink_20260804/20260804_043915_t_marinerush_Kairos_tea_r1_run0/
game_records/matrix450_qwen3_32b_v2_noknowledge_nothink_20260804/20260804_143058_t_marinerush_Kairos_tea_r1_run0/kv2_no_knowledge_traces/2026-08-04/063449_6fad4931d75f/trace.json
game_records/matrix450_qwen3_32b_v2_nothink_20260804/20260804_043931_t_twobasemat_Kairos_tea_r2_run8/
game_records/matrix450_qwen3_32b_v2_noknowledge_nothink_20260804/20260804_144002_t_twobasemat_Kairos_tea_r2_run8/kv2_no_knowledge_traces/2026-08-04/064922_a0fb291e959d/trace.json
```
