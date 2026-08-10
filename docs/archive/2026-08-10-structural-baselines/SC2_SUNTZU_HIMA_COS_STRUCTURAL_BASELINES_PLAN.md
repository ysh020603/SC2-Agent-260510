# SC2-Specific Structural Harness Baselines
## SunTzu + HIMA + Chain-of-Summarization (CoS) 复现实施方案

> **目标仓库**：`https://github.com/ysh020603/SC2-Agent-260510`  
> **目标分支**：`SC2-Agent-knowlegde`  
> **用途**：本文件可直接交给 Code Agent 执行。  
> **目标**：在现有 SC2-Agent 平台中新增 3 个 **SC2-specific structural harness baselines**：
>
> - `suntzu`
> - `hima`
> - `cos`
>
> 本任务**只复现三种方法的 Agent / Harness 控制结构**，不复现原论文的专用模型，不下载 Hugging Face 模型，不部署本地推理服务器，不迁移原仓库的低层 SC2 执行逻辑。
>
> 所有 LLM 调用必须统一使用本仓库已有：
>
> ```python
> from API_Tools.llm_caller import call_openai_detailed
> ```
>
> 且所有角色默认统一使用：
>
> ```text
> self.decision_model_key
> ```
>
> **不要使用、下载、启动或依赖任何第三方模型服务。**

---

# 0. 总体原则

当前平台的公共决策边界保持不变：

```text
Strategy Summary
+ Current Observation
+ Previous Uncommitted Queue
+ Canonical Action Space
        ↓
    Harness
        ↓
{reason, ordered_names}
        ↓
Canonical Mapping
        ↓
ExecutionScheduler
        ↓
SC2 Environment
```

三个新增方法只替换中间：

```text
Harness
```

这一段。

最终都必须回到当前平台已经存在的公共输出：

```json
{
  "reason": "Concise public explanation.",
  "ordered_names": [
    "Marine",
    "SupplyDepot",
    "Barracks"
  ]
}
```

之后继续使用原有：

```text
canonical_race_entity_name
action_candidates_for_entity
ExecutionScheduler
replace_uncommitted_queue
```

**不得为新 baseline 建第二套执行系统。**

---

# 1. 强制约束

Code Agent 必须遵守以下约束。

## 1.1 不修改已有 Harness 内部实现

不要重写、重构或替换：

```text
SC2_Agent/decision_agent.py
SC2_Agent/knowledge_v2_2/
SC2_Agent/knowledge_v2_2_v2/
SC2_Agent/knowledge_v2_2_v2_no_knowledge/
SC2_Agent/knowledge_v2_3/
SC2_Agent/knowledge_v2_3_no_knowledge/
SC2_Agent/execution/
```

中央入口允许做**最小 additive integration**：

```text
dummies/generic/universal_llm_bot.py
run_vs_ai.py
bot_loader/game_starter.py
tools/run_experiment.py
```

只能增加：

```text
new mode constants
new routing branches
new state fields
new trace routing
new CLI choices
```

不要重构原有分支。

---

## 1.2 COPY THEN MODIFY

三个 baseline 都应独立建立 package。

不要让它们共享一套不断变化的 baseline prompt。

可以从：

```text
SC2_Agent/decision_agent.py
```

复制当前公共 SC2 prompt/context 作为起点，再分别修改复制件。

目的是保证：

```text
naive
suntzu
hima
cos
```

未来可以独立审计。

---

## 1.3 只复现结构，不复现专用模型

### SunTzu

不要：

- 下载 SunTzu 原模型；
- 引入其专用 LLMClient；
- 复制其 low-level action representation；
- 复制 unit-id / coordinate action generation；
- 复制 map-dependent control。

### HIMA

明确禁止：

```text
Protoss-a / Protoss-b / Protoss-c
Terran-a / Terran-b / Terran-c
Zerg-a / Zerg-b / Zerg-c
```

以及：

```text
FastAPI local server
requests.post("localhost:...")
transformers model loading
Hugging Face downloads
```

### CoS

不要：

- 创建新的 OpenAI Client；
- 使用原项目的旧 API；
- 下载 embedding/model；
- 复制 TextStarCraft II 的低层 environment；
- 复制原 action mixing / empty-action timing system。

---

## 1.4 所有模型调用统一走仓库 API

必须统一：

```python
call_openai_detailed(
    messages=messages,
    model_key=self.decision_model_key,
)
```

或者在各 baseline package 内封装一个：

```python
LLMInvoker
```

但底层必须仍调用：

```python
API_Tools.llm_caller.call_openai_detailed
```

禁止：

```python
OpenAI(...)
requests.post(...)
transformers.AutoModel...
vllm local model...
```

---

## 1.5 不接入 Knowledge Layer

三个 baseline 的实现目录中禁止依赖：

```text
DataSubAgent
knowledge_v2_2
knowledge_v2_3
dataset_store
search_tools
knowledge cache
knowledge ledger
retrieval
RAG
```

验收：

```bash
git grep -n -E \
  "DataSubAgent|knowledge_v2|dataset_store|search_tools|RagAgent|requests.post|AutoModelForCausalLM" \
  SC2_Agent/baseline_suntzu \
  SC2_Agent/baseline_hima \
  SC2_Agent/baseline_cos
```

Python implementation 中不应出现实际依赖。

---

# 2. Research Gate：写代码前先复核原方法

在开始 Python 实现前，新建：

```text
docs/sc2_structural_baselines/
├── SUNTZU_REPRODUCTION_NOTES.md
├── HIMA_REPRODUCTION_NOTES.md
└── COS_REPRODUCTION_NOTES.md
```

必须先写完这三个文件。

---

# 3. SunTzu 调研来源

官方仓库：

```text
https://github.com/yorhaha/SunTzu
```

重点阅读：

```text
README.md
players/llm_player.py
agents/plan_agent.py
agents/action_agent.py
agents/single_agent.py
players/base_player.py
```

原方法的核心结构需要在研究记录中明确：

```text
Observation
   ↓
Planner
   ↓
High-level Natural-Language Plan
   ↓
Plan Verifier / Critic
   ↓
if invalid:
    Refine Plan
   ↓
Executor
   ↓
Low-level Actions
   ↓
Action Verifier
   ↓
if invalid:
    Refine Actions
   ↓
Execute
```

尤其确认：

```text
PlanAgent:
generate plan
→ critic plan
→ refine plan
→ repeat

ActionAgent:
generate actions
→ deterministic verifier
→ feed verifier errors back
→ regenerate
```

原代码中：

```text
max_refine_times = 3
max_retry_attempts = 3
```

这两个数字作为原方法参考。

---

# 4. HIMA 调研来源

官方仓库：

```text
https://github.com/snumprlab/hima
```

论文：

```text
Society of Mind Meets Real-Time Strategy:
A Hierarchical Multi-Agent Framework for Strategic Reasoning
COLM 2025
```

重点阅读：

```text
README.md
app.py
bot.py
prompt.py
prompts/multi_lm_prompt.py
```

必须确认结构：

```text
                 Observation
                      │
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
    Advisor A     Advisor B     Advisor C
        │             │             │
        └─────────────┼─────────────┘
                      ↓
                    Leader
                      ↓
               Final Decision
```

原实现通过：

```text
Suggestion A
Suggestion B
Suggestion C
```

传给 Leader。

Leader 的核心不是简单投票，而是：

```text
Agreed Viewpoints
Conflicted Viewpoints
Resolve Conflicts
Isolated Viewpoints
Final Strategic Direction
```

本项目必须保留：

> 多个相互独立 advisor → leader 综合冲突与共识 → 最终决策

这一结构。

---

# 5. CoS 调研来源

原论文：

```text
Large Language Models Play StarCraft II:
Benchmarks and A Chain of Summarization Approach
```

官方仓库：

```text
https://github.com/histmeisah/Large-Language-Models-play-StarCraftII
```

HIMA 仓库中也带有可参考 implementation：

```text
snumprlab/hima/bots/textstarcraft.py
snumprlab/hima/prompts/agent_prompt.py
```

必须确认 CoS 的核心：

```text
Raw Observation_t
       ↓
Single-frame / L1 Summary_t
       ↓
Rolling Summary Memory
       ↓
Recent K L1 Summaries
       ↓
Multi-frame / L2 Summary
       ↓
Strategic Decision
```

HIMA 内的参考实现使用：

```text
last_k = 5
```

本项目主 baseline 默认同样使用：

```python
COS_HISTORY_SIZE = 5
```

---

# 6. 三种方法在本平台中的统一复现边界

三个方法均共享：

```text
same Strategy Summary
same Current Observation
same old uncommitted queue
same canonical unit names
same canonical upgrade names
same race context
same strategy automation context
same decision interval
same trigger
same scheduler
same mapper
same SC2 scripts
```

不同的只有 Harness。

---

# 7. 新增代码目录

建议新增：

```text
SC2_Agent/
├── baseline_suntzu/
│   ├── __init__.py
│   ├── decision_prompt.py
│   ├── planner_prompt.py
│   ├── plan_verifier_prompt.py
│   ├── executor_prompt.py
│   ├── schemas.py
│   ├── verifier.py
│   ├── agent.py
│   ├── trace.py
│   ├── README.md
│   └── SOURCE_NOTES.md
│
├── baseline_hima/
│   ├── __init__.py
│   ├── decision_prompt.py
│   ├── advisor_prompt.py
│   ├── leader_prompt.py
│   ├── schemas.py
│   ├── agent.py
│   ├── trace.py
│   ├── README.md
│   └── SOURCE_NOTES.md
│
└── baseline_cos/
    ├── __init__.py
    ├── decision_prompt.py
    ├── l1_prompt.py
    ├── l2_prompt.py
    ├── schemas.py
    ├── state.py
    ├── agent.py
    ├── trace.py
    ├── README.md
    └── SOURCE_NOTES.md
```

---

# 8. Prompt 基础：从当前 naive 复制

执行：

```bash
mkdir -p SC2_Agent/baseline_suntzu
mkdir -p SC2_Agent/baseline_hima
mkdir -p SC2_Agent/baseline_cos
```

复制：

```bash
cp SC2_Agent/decision_agent.py \
   SC2_Agent/baseline_suntzu/decision_prompt.py

cp SC2_Agent/decision_agent.py \
   SC2_Agent/baseline_hima/decision_prompt.py

cp SC2_Agent/decision_agent.py \
   SC2_Agent/baseline_cos/decision_prompt.py
```

然后分别修改复制件。

保留当前平台公共的：

```text
Agent Role And Responsibility Boundary
Decision Lifecycle
Queue And Commitment Semantics
Race Identity And Mechanics
Economy And Production Principles
Strategy Objective
Automated Strategy Behaviors
Observation Field Guide
Allowed Macro Outputs
Canonical names
Near-term horizon
```

不要让任一 baseline 获得额外 SC2 知识。

---

# 9. Baseline A — SunTzu Structural Reproduction

CLI：

```text
--decision-agent-mode suntzu
```

Package：

```text
SC2_Agent/baseline_suntzu/
```

---

# 10. SunTzu 在本平台中的流程

复现：

```text
Frozen Decision Context
        ↓
      Planner
        ↓
 Semantic Macro Plan
        ↓
  LLM Plan Verifier
        ↓
  errors?
   │   │
  no  yes
   │   ↓
   │ Plan Refiner
   │   │
   └───┘
        ↓
      Executor
        ↓
Candidate ordered_names
        ↓
Deterministic Queue Verifier
        ↓
 invalid?
   │      │
  no     yes
   │      ↓
   │ Executor Refine
   │      │
   └──────┘
        ↓
{reason, ordered_names}
        ↓
Existing Mapping + Scheduler
```

---

# 11. SunTzu：Frozen Context

一次 macro decision 内：

```text
Observation 只 capture 一次。
```

所有：

```text
Planner
Plan Verifier
Plan Refiner
Executor
Executor Retry
```

必须使用同一份：

```text
obs_text
strategy_summary
old_uncommitted_queue
canonical lists
```

严禁在 refinement 中重新读取环境。

---

# 12. SunTzu Planner

职责：

> 从当前 frozen SC2 context 中形成 high-level semantic macro commands。

不要直接生成 canonical queue。

建议 schema：

```json
{
  "plan_reason": "Stabilize immediate defense before resuming economy.",
  "commands": [
    "Increase immediately available combat production.",
    "Prevent near-term supply blocking.",
    "Resume worker production after military stabilization."
  ]
}
```

要求：

```text
1–5 semantic commands
short public statements
no hidden chain-of-thought
no positions
no workers/producers
```

---

# 13. SunTzu Plan Verifier

读取：

```text
frozen context
+
candidate semantic plan
```

输出：

```json
{
  "error_number": 2,
  "errors": [
    "The plan neglects near-term supply pressure.",
    "The plan expands economy before handling the visible military threat."
  ]
}
```

或者：

```json
{
  "error_number": 0,
  "errors": []
}
```

Verifier 只能依据：

```text
当前公共 prompt policy
当前 observation
当前 strategy summary
```

禁止使用额外知识表。

---

# 14. SunTzu Plan Refinement

如果：

```text
error_number > 0
```

调用一次 Plan Refiner：

输入：

```text
original frozen context
original/current plan
verifier errors
```

输出完整的新 semantic plan。

循环：

```python
SUNTZU_MAX_PLAN_REFINE = 3
```

与原 SunTzu 的 `max_refine_times = 3` 对齐。

停止：

```text
plan_verified
max_plan_refine
plan_verifier_invalid
plan_refine_invalid
```

---

# 15. SunTzu Executor

读取：

```text
frozen context
+
verified/final semantic plan
```

输出：

```json
{
  "reason": "Execute the verified defensive-production plan first.",
  "ordered_names": [
    "Marine",
    "Marine",
    "SupplyDepot",
    "Barracks"
  ]
}
```

这是**完整 replacement queue**。

不是 fragment。

---

# 16. SunTzu Action Verifier 的结构适配

原 SunTzu Action Verifier 会对 low-level actions 检查：

```text
unit id
ability
resource
supply
target
position
```

本平台不应该复制这些 low-level mechanics。

因此这里只复现：

> **Executor Output → Deterministic Verification → Error Feedback → Executor Retry**

的结构。

实现一个：

```python
verify_macro_queue(...)
```

只做**公共接口层验证**：

```text
JSON schema valid
reason non-empty
ordered_names is list[str]
each name is exact canonical candidate
queue length <= 20
no empty names
```

不要检查：

```text
具体 worker
具体 producer
位置
resource simulation
combat counter
gas formulas
production throughput
```

因为这些属于平台执行层或额外 heuristic。

---

# 17. SunTzu Executor Retry

若 verifier 返回：

```json
{
  "valid": false,
  "errors": [...]
}
```

把 errors 返回给同一个 Executor LLM：

```text
previous candidate
+
deterministic validation errors
+
generate a complete corrected queue
```

默认：

```python
SUNTZU_MAX_EXECUTOR_RETRY = 3
```

对齐原 SunTzu `max_retry_attempts = 3`。

---

# 18. SunTzu 失败策略

### Planner invalid

```text
whole decision invalid
keep old queue
```

### Plan Verifier invalid

接受当前 last valid plan，继续 Executor：

```text
stop_reason = plan_verifier_invalid
```

### Plan Refiner invalid

保留上一个 valid plan，继续 Executor。

### Executor initial output invalid

进入 verifier/retry。

### Executor retries exhausted

如果存在 last syntactically valid candidate：

```text
use last valid candidate
```

如果一个 valid candidate 都没有：

```text
whole decision invalid
keep old queue
```

---

# 19. SunTzu 模型调用

所有角色：

```text
Planner
Plan Verifier
Plan Refiner
Executor
Executor Retry
```

统一：

```text
decision_model_key
```

不要给 verifier 单独模型。

---

# 20. SunTzu Trace

目录：

```text
<match>/suntzu_traces/
```

至少：

```json
{
  "mode": "suntzu",
  "plan_initial": {},
  "plan_refine_rounds": [],
  "plan_stop_reason": "plan_verified",
  "executor_initial": {},
  "executor_verification_rounds": [],
  "executor_stop_reason": "queue_verified",
  "final_decision": {},
  "model_call_count": 5,
  "status": "completed"
}
```

每个 subcall 记录：

```text
role
messages
content
raw_content
provider reasoning
model key
latency
error
```

---

# 21. Baseline B — HIMA Structural Reproduction

CLI：

```text
--decision-agent-mode hima
```

Package：

```text
SC2_Agent/baseline_hima/
```

---

# 22. HIMA 在本平台中的结构

复现：

```text
                  Frozen Context
                       │
         ┌─────────────┼─────────────┐
         ↓             ↓             ↓
     Advisor A     Advisor B     Advisor C
         │             │             │
         └─────────────┼─────────────┘
                       ↓
                     Leader
                       ↓
             {reason, ordered_names}
                       ↓
           Existing Mapper/Scheduler
```

---

# 23. HIMA 不使用原 imitation models

原 HIMA：

```text
model-a
model-b
model-c
+
Leader LLM
```

本项目结构版：

```text
same API model
same API model
same API model
+
same API model Leader
```

全部：

```text
decision_model_key
```

---

# 24. HIMA Advisor Independence

三个 advisor 必须：

```text
相互看不到彼此输出。
```

即：

```text
Advisor A(context)
Advisor B(context)
Advisor C(context)
```

不能：

```text
Advisor B(context + A)
Advisor C(context + A + B)
```

否则就不再是 HIMA-style independent deliberation。

---

# 25. HIMA Advisor Prompt

Advisor 读取：

```text
same frozen observation
same Strategy Summary
same carry-over queue
same canonical lists
```

推荐输出：

```json
{
  "advisor": "A",
  "assessment": "Immediate pressure requires military stabilization.",
  "suggested_actions": [
    "Marine",
    "Marine",
    "SupplyDepot",
    "Barracks"
  ]
}
```

其中：

```text
assessment = concise public strategic rationale
suggested_actions = canonical names only
```

---

# 26. Advisor A/B/C 是否采用不同角色？

主实验建议：

> 不赋予 A/B/C 不同的额外 SC2 expert knowledge。

仅使用相同任务 prompt，并标识：

```text
You are Advisor A/B/C.
Provide an independent recommendation.
Do not assume access to other advisors.
```

这样保持：

```text
same information
same model
independent inference
```

不要人工写成：

```text
A = economy expert
B = military expert
C = technology expert
```

因为这会人为增加新的角色知识设计。

---

# 27. HIMA “并行”的实现

原 HIMA 在代码层面并行推理三个模型。

结构复现的核心是：

```text
independent advisors
```

而不是 wall-clock concurrency。

因此首版允许：

```python
for advisor in ("A", "B", "C"):
    call_openai_detailed(...)
```

顺序执行。

但必须保证：

```text
A/B/C 输入互不包含彼此输出。
```

在文档中称为：

```text
logical parallel / independent advisor generation
```

不要为了并行修改整个游戏 event loop。

如果之后需要降低 latency，可另开任务做线程并行。

---

# 28. HIMA Leader

Leader 输入：

```text
frozen context
+
Advisor A
+
Advisor B
+
Advisor C
```

必须保留 HIMA 的核心聚合逻辑：

```text
1. identify agreed viewpoints
2. identify conflicted viewpoints
3. resolve conflicts
4. identify isolated but useful viewpoints
5. form final strategic direction
6. output final canonical queue
```

Leader 最终只返回：

```json
{
  "reason": "The advisors agree on immediate army reinforcement; expansion is delayed.",
  "ordered_names": [
    "Marine",
    "Marine",
    "SupplyDepot",
    "Barracks"
  ]
}
```

不要再多一个 Finalizer。

---

# 29. HIMA Advisor Failure

若某一个 advisor malformed：

```text
do not fail whole decision
```

将其记录为：

```text
advisor_status = invalid
```

Leader 可以使用剩余 valid advisors。

要求：

```text
至少 1 个 valid advisor
```

否则：

```text
whole decision invalid
keep old queue
```

Leader prompt 中必须明确：

```text
Only use valid advisor outputs supplied below.
```

---

# 30. HIMA Leader Failure

若 Leader output 无法 parse：

```text
whole decision invalid
keep old queue
```

不增加额外 repair call。

HIMA baseline 的核心不是 Self-Refine。

---

# 31. HIMA 调用数

正常固定：

```text
3 Advisor calls
+
1 Leader call
=
4 calls / decision
```

必须记录。

---

# 32. HIMA Trace

目录：

```text
<match>/hima_traces/
```

结构：

```json
{
  "mode": "hima",
  "advisors": [
    {
      "advisor": "A",
      "output": {},
      "valid": true
    },
    {
      "advisor": "B",
      "output": {},
      "valid": true
    },
    {
      "advisor": "C",
      "output": {},
      "valid": true
    }
  ],
  "leader_input": {},
  "leader_output": {},
  "final_decision": {},
  "valid_advisor_count": 3,
  "model_call_count": 4
}
```

---

# 33. Baseline C — Chain of Summarization (CoS)

CLI：

```text
--decision-agent-mode cos
```

Package：

```text
SC2_Agent/baseline_cos/
```

---

# 34. CoS 在本平台中的结构

```text
Decision t:
Current Observation_t
        ↓
      L1
single-frame summary
        ↓
append to rolling history
        ↓
[L1_t-4, L1_t-3, L1_t-2, L1_t-1, L1_t]
        ↓
      L2
multi-frame synthesis
        ↓
{reason, ordered_names}
        ↓
Existing Mapper/Scheduler
```

这里 CoS 与前两个不同：

```text
SunTzu / HIMA
主要改变一次 decision 内部 orchestration

CoS
主要改变跨 decision 的 context management
```

---

# 35. CoS State

新增：

```python
@dataclass
class CoSState:
    l1_history: list[dict]
    max_history: int = 5
```

或同等明确实现。

状态：

```text
仅在一局 match 内存在。
```

必须：

```text
new game → empty history
```

禁止：

```text
跨 game memory
持久化经验
retrieval memory
knowledge cache
```

---

# 36. CoS History Size

主实验固定：

```python
COS_HISTORY_SIZE = 5
```

理由：

- HIMA 仓库内 TextStarCraft reference implementation 使用 `last_k = 5`；
- 这是 structural reproduction 的可解释默认值。

不要把 K 做成自动调参。

可以允许 CLI/config override，但主实验使用 5。

---

# 37. CoS L1 Summarizer

每次 macro decision：

```text
Current Observation
→ L1 Summary
```

L1 只总结当前 frame。

不能读取：

```text
previous L1 history
previous decisions
future state
knowledge database
```

推荐 schema：

```json
{
  "game_time": 360.0,
  "economy": "Mineral bank is high; worker saturation is moderate.",
  "production": "Barracks capacity is limited.",
  "army": "Current army is small relative to visible pressure.",
  "enemy": "Visible enemy ground pressure is increasing.",
  "supply": "Near-term supply block risk exists.",
  "committed_work": "One Barracks is already under construction.",
  "strategic_signal": "Prioritize stabilization and spending."
}
```

这是**public summary artifact**。

不要要求模型暴露 chain-of-thought。

---

# 38. CoS L1 输入

L1 应看：

```text
current obs_text
current decision cycle/time
race context
```

为了公平性，可以给：

```text
Strategy Summary
```

但在 prompt 中要求：

```text
summarize the current frame faithfully;
do not invent actions.
```

L1 不产生 queue。

---

# 39. CoS L2

L2 输入：

```text
Strategy Summary
Current Decision Event
Current old uncommitted queue
Recent <=5 L1 summaries
Canonical action lists
```

L2 直接承担：

```text
multi-frame strategic synthesis
+
final decision
```

不要再增加第三个 Decision Agent。

否则会变成：

```text
L1 → L2 → Decision
```

而与原 CoS 的 L2 commander 含义偏离。

本项目使用：

```text
L1 → L2/Commander
```

---

# 40. CoS L2 输出

直接：

```json
{
  "reason": "Across the last several decisions, minerals have remained high while army production stayed low, so increase production and spend on army first.",
  "ordered_names": [
    "Barracks",
    "Marine",
    "Marine",
    "Marine",
    "SupplyDepot"
  ]
}
```

---

# 41. CoS First Decision

第一个 decision 时只有：

```text
1 个 L1 summary
```

仍然直接调用 L2。

不要等待 history 填满 5。

所以：

```text
cycle 1 → history size 1
cycle 2 → history size 2
...
cycle 5 → history size 5
cycle 6 → keep latest 5
```

---

# 42. CoS History 更新时机

推荐：

```text
1. capture observation
2. generate valid L1
3. append L1 to history
4. trim to last K
5. run L2
```

即使 L2 最终 decision invalid：

```text
valid L1 仍然可以保留
```

因为它是当前真实 observation 的摘要。

如果 L1 invalid：

```text
do not append invalid L1
```

L2 可以：

- 若已有旧 history：使用 old history + raw current observation fallback；
- 若没有 history：整个 decision invalid。

为了简单、可审计，首版建议：

```text
L1 invalid → whole decision invalid, keep old queue
```

避免额外 fallback 引入新结构。

---

# 43. CoS 调用数

正常固定：

```text
1 L1 call
+
1 L2 call
=
2 calls / macro decision
```

---

# 44. CoS Trace

目录：

```text
<match>/cos_traces/
```

结构：

```json
{
  "mode": "cos",
  "history_size_before": 4,
  "l1_current": {},
  "history_after": [
    "...up to five summaries..."
  ],
  "l2_output": {},
  "final_decision": {},
  "model_call_count": 2
}
```

---

# 45. Shared Baseline Runtime Helper

为了避免三个 package 各自重复 API boilerplate，可以新增：

```text
SC2_Agent/baseline_common/
├── __init__.py
├── llm.py
└── trace.py
```

**仅允许放结构无关的 utility**：

```text
call_openai_detailed wrapper
wall-time measurement
subcall trace serialization
safe JSON extraction
```

不要把：

```text
SC2 decision prompt
SC2 rules
canonical validation
state
method-specific schema
```

放进 `baseline_common`。

---

# 46. Common LLMInvoker

建议：

```python
class BaselineLLMInvoker:
    def __init__(self, model_key, recorder):
        ...

    def call(self, *, role, messages):
        ...
```

内部：

```python
result = call_openai_detailed(
    messages=messages,
    model_key=self.model_key,
)
```

trace：

```text
role
seq
model_key
model
content
raw_content
reasoning
reasoning_source
is_reasoning
error
latency
prompt_chars
output_chars
```

---

# 47. 统一 run_decision API

建议三个 package 都提供：

```python
def run_decision(
    *,
    context: dict,
    provider: str,
    log_dir: str | None = None,
    state: object | None = None,
) -> dict:
    ...
```

返回：

```python
{
    "agent_version": "...",
    "decision": {
        "reason": "...",
        "ordered_names": [...]
    },
    "llm_calls": [...],
    "orchestration": {...},
    "log_path": "...",
}
```

CoS 额外：

```python
{
    "state": updated_cos_state
}
```

或者直接原地更新传入 state。

---

# 48. Central Integration

修改：

```text
dummies/generic/universal_llm_bot.py
```

只做 additive integration。

新增：

```python
SUNTZU_DECISION_AGENT_MODE = "suntzu"
HIMA_DECISION_AGENT_MODE = "hima"
COS_DECISION_AGENT_MODE = "cos"
```

加入：

```python
SUPPORTED_DECISION_AGENT_MODES
```

---

# 49. CoS Runtime State

在 `UniversalLLMBot.__init__` 中增加：

```python
self._cos_state = None
```

或：

```python
self._cos_state = {
    "l1_history": []
}
```

只供：

```text
mode == "cos"
```

使用。

不要影响其它 mode。

`on_start` 时重置。

---

# 50. Dispatch 推荐结构

不要继续把所有方法塞进现有：

```text
if knowledge...
else naive
```

中难以维护。

但也不要大规模重构。

只在现有 decision pipeline 的 knowledge/naive 分支之前增加三个清晰 branch：

```python
if mode == "suntzu":
    ...
elif mode == "hima":
    ...
elif mode == "cos":
    ...
elif mode in EXISTING_KNOWLEDGE_MODES:
    ... existing code unchanged ...
else:
    ... existing naive code unchanged ...
```

重点：

> 把 existing knowledge block 和 naive block 尽量原样保留。

---

# 51. 调用当前 Frozen Observation

当前 `UniversalLLMBot` 已经：

```python
obs_text, obs_snapshot = self._capture_observation_bundle()
```

然后构造统一：

```python
prompt_arguments = dict(...)
```

三个 baseline 都应复用**这一份捕获结果**。

不要在 baseline agent 内重新访问 bot/environment。

---

# 52. Structural Context Object

推荐中央入口构造：

```python
structural_context = {
    "race": self.race_name,
    "strategy_summary": self.strategy_summary,
    "obs_text": obs_text,
    "observation_structured": obs_snapshot,
    "unfinished_canonical_names": old_names,
    "canonical_unit_names": race_unit_names(self.race_name),
    "canonical_upgrade_names": race_upgrade_names(self.race_name),
    "race_context": race_prompt_context(self.race_name),
    "strategy_automation_context": self.strategy_automation_context,
    "decision_cycle": self._decision_cycle_count,
    "trigger_reason": trigger_reason,
    "game_time_seconds": game_time,
    "decision_interval_seconds": self.decision_interval_seconds,
    "enemy_race": self.strategy_enemy_race,
}
```

三个 baseline 都收到同一种 context。

---

# 53. 公共最终映射不变

baseline 返回：

```python
decision_payload = result["decision"]
parsed = MacroDecision(
    reason=...,
    ordered_names=...
)
```

之后必须继续运行现有：

```text
canonical_race_entity_name
_action_candidates_for_entity
scheduler.replace_uncommitted_queue
_queue_transition
```

不要在 baseline package 内 replace scheduler queue。

---

# 54. `.llm_calls.json` 多调用记录

当前 naive 只记录一条 call。

新增一个**只服务于 structural baseline** 的 helper，例如：

```python
def _record_structural_baseline_calls(self, result):
    ...
```

将：

```python
result["llm_calls"]
```

每一条加入：

```python
self._llm_call_records
```

角色命名：

SunTzu：

```text
suntzu.planner
suntzu.plan_verifier
suntzu.plan_refiner
suntzu.executor
suntzu.executor_retry
```

HIMA：

```text
hima.advisor_a
hima.advisor_b
hima.advisor_c
hima.leader
```

CoS：

```text
cos.l1
cos.l2
```

不要改变现有 naive / knowledge mode 的日志语义。

---

# 55. schema_version

建议 structural SC2 baselines：

```text
schema_version = 5
```

只影响：

```text
suntzu
hima
cos
```

旧 mode 保持原值。

---

# 56. CLI 接入

只 append choices。

修改：

```text
run_vs_ai.py
bot_loader/game_starter.py
tools/run_experiment.py
```

加入：

```text
suntzu
hima
cos
```

不要修改：

```text
DEFAULT_DECISION_AGENT_MODE
```

---

# 57. 不新增 HIMA 模型参数

不要新增：

```text
--advisor-model-a
--advisor-model-b
--advisor-model-c
--hima-server
--hima-port
```

HIMA 所有角色使用：

```text
--decision-model
```

---

# 58. 不新增 SunTzu 模型参数

不要新增：

```text
--planner-model
--verifier-model
--executor-model
```

全部使用：

```text
--decision-model
```

---

# 59. 不新增 CoS summary model 参数

不要新增：

```text
--l1-model
--l2-model
```

全部使用：

```text
--decision-model
```

---

# 60. 测试目录

新增：

```text
tools/tests/
├── test_suntzu_structural_baseline.py
├── test_hima_structural_baseline.py
├── test_cos_structural_baseline.py
└── test_sc2_structural_baseline_routing.py
```

不要删除/重写旧测试。

---

# 61. SunTzu Unit Tests

必须覆盖：

## Plan

```text
valid plan parse
invalid plan JSON
empty commands
too many commands
```

## Plan verifier

```text
error_number = 0
error_number > 0
malformed verifier
```

## Refinement

Mock call order：

```text
Planner
→ PlanVerifier
→ PlanRefiner
→ PlanVerifier
→ Executor
```

assert exact order。

## Max refinement

验证最多：

```text
3 plan refinements
```

## Action verifier

测试：

```text
valid canonical queue
unknown canonical name
queue > 20
invalid reason
invalid list
```

## Executor retry

验证：

```text
Executor
→ deterministic verifier failure
→ Executor retry
```

最多 3 次。

## Frozen observation

所有 LLM subcall 中 current observation 完全相同。

---

# 62. HIMA Unit Tests

必须覆盖：

## Independent advisors

Mock：

```text
A
B
C
```

assert：

```text
B input does not contain A output
C input does not contain A/B output
```

## Leader

assert Leader 输入包含：

```text
A
B
C
```

## One advisor invalid

```text
A valid
B invalid
C valid
→ Leader still runs
```

## All invalid

```text
whole decision invalid
```

## Leader malformed

```text
whole decision invalid
```

## Call count

normal:

```text
4 calls
```

## Same model

所有 call：

```text
model_key == configured decision model
```

---

# 63. CoS Unit Tests

必须覆盖：

## First cycle

```text
L1 → history size 1 → L2
```

## Fifth cycle

```text
history size 5
```

## Sixth cycle

只保留：

```text
latest 5
```

## L1 isolation

L1 prompt 不包含旧 L1 history。

## L2 temporal input

L2 能看到最近 K 个 summary。

## Match reset

新的 CoSState：

```text
history = []
```

## Invalid L1

```text
decision invalid
history unchanged
```

## Invalid L2

```text
L1 remains in history
decision invalid
old queue remains
```

## Call count

正常：

```text
2 calls / decision
```

---

# 64. Mock API 优先

所有 unit tests monkeypatch：

```python
call_openai_detailed
```

禁止测试依赖真实 API。

先验证：

```text
state machine
call ordering
schemas
fallback
trace
routing
```

再跑 real API probe。

---

# 65. 新增 Probe

新增：

```text
tools/probe_sc2_structural_baselines.py
```

支持：

```bash
python tools/probe_sc2_structural_baselines.py \
  --decision-agent-mode suntzu \
  --model-key DeepSeek-V4-flash
```

```bash
python tools/probe_sc2_structural_baselines.py \
  --decision-agent-mode hima \
  --model-key DeepSeek-V4-flash
```

```bash
python tools/probe_sc2_structural_baselines.py \
  --decision-agent-mode cos \
  --model-key DeepSeek-V4-flash
```

不要修改已有 knowledge probes。

---

# 66. Probe Scenarios

至少：

```text
Terran
Protoss
Zerg
```

各一个 frozen scenario。

每个 scenario 提供：

```text
strategy summary
observation
old uncommitted queue
canonical names
```

验证结构，不验证“唯一正确策略”。

---

# 67. CoS Probe 需要多 cycle

CoS probe 需要至少模拟：

```text
6 consecutive macro decisions
```

确保：

```text
1 → 2 → 3 → 4 → 5 → 5 history window
```

并验证旧 summary 正确淘汰。

---

# 68. Real-Match Smoke Tests

结构 probe 全部通过后：

```text
3 races
×
3 new baselines
=
9 smoke matches
```

首轮可以缩短：

```text
SC2_GAME_TIME_LIMIT = 300–600 seconds
```

验证：

```text
no crash
no routing error
trace saved
queue accepted
scheduler unaffected
```

---

# 69. Regression

必须执行：

```bash
python -m compileall \
  SC2_Agent \
  dummies/generic \
  bot_loader \
  tools \
  run_vs_ai.py
```

再：

```bash
python -m pytest tools/tests -q -p no:cacheprovider
```

要求：

```text
all old tests pass
all new tests pass
```

---

# 70. 正式实验的比较对象

最终可形成：

```text
Generic Structural Baselines
----------------------------
naive
plan-execute
self-refine

SC2-Specific Structural Baselines
---------------------------------
suntzu
hima
cos

Ours
----
proposed harness
```

---

# 71. 三种 SC2 Baseline 各自回答的问题

## SunTzu

测试：

> 对 SC2 决策做 hierarchical generation，并对 plan 和 executable decision 分别 self-correct，是否有效？

结构特征：

```text
hierarchy
+
verification
+
iterative correction
```

---

## HIMA

测试：

> 多个独立 strategic opinions 再由 Leader 做共识/冲突整合，是否优于单 Agent？

结构特征：

```text
multi-agent deliberation
+
aggregation
```

---

## CoS

测试：

> 用压缩后的多时间步状态历史代替单帧决策，是否有助于 long-horizon SC2 reasoning？

结构特征：

```text
temporal context management
+
hierarchical summarization
```

---

# 72. 公平性要求

正式比较固定：

| Variable | Requirement |
|---|---|
| Base LLM | same |
| API profile | same |
| Strategy Summary | same |
| Decision interval | same |
| Trigger logic | same |
| Observation source | same |
| Canonical action space | same |
| Mapper | same |
| Scheduler | same |
| SC2 micro scripts | same |
| Maps | paired |
| Opponents | paired |
| Seeds | paired where supported |
| Knowledge retrieval | OFF |
| External model | NONE |
| Cross-game memory | OFF |

---

# 73. 计算成本必须单独报告

因为：

```text
naive ≈ 1 call
CoS ≈ 2 calls
HIMA = 4 calls
SunTzu = variable multi-call
```

必须记录：

```text
LLM calls / decision
wall latency / decision
prompt chars
output chars
reasoning mode
```

如果以后统一支持 exact token usage，再给所有 harness 一起补。

不要只给新 baseline 统计 exact tokens。

---

# 74. 主实验不强制 call-budget matching

第一版论文实验可以先报告：

```text
native harness setting
```

即每个结构按照原本自然调用次数运行。

同时必须显式报告 inference cost。

如果 reviewer 对计算量敏感，再增加：

```text
budget-controlled comparison
```

作为补充实验。

---

# 75. 方法命名建议

代码 mode：

```text
suntzu
hima
cos
```

论文表格：

```text
SunTzu-HSCF
HIMA-Structure
CoS
```

其中：

```text
HIMA-Structure
```

用于明确：

> 我们只复现 HIMA 的 Society-of-Mind aggregation structure，不使用其 imitation-trained advisor models。

---

# 76. SOURCE_NOTES 必须说明 adaptation

## SunTzu

写明：

```text
Original:
Planner → LLM Plan Verifier → Executor → deterministic low-level Action Verifier

Our structural adaptation:
Planner → LLM Plan Verifier → Macro Queue Executor → deterministic macro contract verifier

Removed:
unit-id selection
coordinates
low-level ability validation
map control logic
```

---

## HIMA

写明：

```text
Original:
three distinct imitation advisor models → leader LLM

Our structural adaptation:
three independent calls to the same configured API model → same-model leader

Removed:
downloaded race-specific models
FastAPI inference service
Hugging Face dependency
```

---

## CoS

写明：

```text
Original:
raw frame → L1 → rolling L1 summaries → L2 commander → TextStarCraft actions

Our structural adaptation:
current platform observation → L1 → rolling five L1 summaries → L2 commander → canonical macro queue

Removed:
TextStarCraft environment
empty-action mixing
legacy action timing
Protoss-only low-level action dictionary
```

---

# 77. 明确禁止迁移的原项目内容

不要复制：

## SunTzu

```text
low-level unit id action JSON
coordinate target generation
full base_player action execution
unit ability tables
map geometry
```

## HIMA

```text
model-a/b/c
FastAPI app
requests inference
race model checkpoints
Ancient Cistern hardcoded map points
race-specific combat scripts
```

## CoS

```text
TextStarCraft low-level action environment
empty action injection
action_mix_rate
action_window
legacy queue pacing
Protoss hardcoded action list
```

这些都不是本任务要比较的 Harness 结构。

---

# 78. 实施阶段

## Phase 0 — Repository Audit

执行：

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

记录：

```text
branch
commit
working tree changes
```

不得覆盖用户已有修改。

---

## Phase 1 — Research Gate

完成：

```text
SUNTZU_REPRODUCTION_NOTES.md
HIMA_REPRODUCTION_NOTES.md
COS_REPRODUCTION_NOTES.md
```

先说明：

```text
original structure
essential invariant
discarded implementation details
SC2-Agent adaptation
```

---

## Phase 2 — Common Utilities

可选新增：

```text
baseline_common/llm.py
baseline_common/trace.py
```

不得碰现有 `API_Tools/llm_caller.py`。

---

## Phase 3 — SunTzu

实现顺序：

```text
schemas
planner prompt
plan verifier
plan refinement
executor
macro verifier
executor retry
trace
mock tests
```

---

## Phase 4 — HIMA

实现：

```text
advisor schema
advisor prompt
3 independent calls
leader prompt
leader aggregation
trace
mock tests
```

---

## Phase 5 — CoS

实现：

```text
CoSState
L1 schema
L1 prompt
history window
L2 prompt
L2 decision
trace
mock tests
```

---

## Phase 6 — Additive Routing

加入：

```text
suntzu
hima
cos
```

到 central runtime 与 CLI。

旧 branch 原样保留。

---

## Phase 7 — Static Tests

运行：

```text
compileall
pytest
```

---

## Phase 8 — Structural Probe

```text
3-race SunTzu
3-race HIMA
6-cycle CoS
```

---

## Phase 9 — Match Smoke

```text
9 short matches
```

确认稳定后再做正式 batch。

---

# 79. 最终验收 Checklist

## Repository Preservation

- [ ] existing naive implementation unchanged
- [ ] existing knowledge packages unchanged
- [ ] scheduler unchanged
- [ ] mapper unchanged
- [ ] observation recorder unchanged
- [ ] default mode unchanged
- [ ] old CLI commands still work

## API

- [ ] all new calls use `call_openai_detailed`
- [ ] no local inference server
- [ ] no Hugging Face model download
- [ ] no direct OpenAI client in baseline packages
- [ ] no requests-based HIMA service
- [ ] all roles use `decision_model_key`

## SunTzu

- [ ] Planner exists
- [ ] LLM Plan Verifier exists
- [ ] plan refinement loop exists
- [ ] max plan refine = 3
- [ ] Executor exists
- [ ] deterministic macro queue verifier exists
- [ ] executor retry loop exists
- [ ] max executor retry = 3
- [ ] all subcalls use frozen observation
- [ ] final output is MacroDecision

## HIMA

- [ ] 3 advisors
- [ ] advisors independent
- [ ] advisors use same model
- [ ] Leader sees all valid advisor outputs
- [ ] Leader resolves agreement/conflict/isolated views
- [ ] no downloaded advisor models
- [ ] normal call count = 4
- [ ] final output is MacroDecision

## CoS

- [ ] L1 single-frame summary
- [ ] rolling history
- [ ] default history size = 5
- [ ] L2 consumes recent summaries
- [ ] L2 directly emits final decision
- [ ] state resets every match
- [ ] no cross-game memory
- [ ] normal call count = 2
- [ ] final output is MacroDecision

## Logging

- [ ] every subcall recorded
- [ ] `suntzu_traces/`
- [ ] `hima_traces/`
- [ ] `cos_traces/`
- [ ] role recorded
- [ ] model key recorded
- [ ] latency recorded
- [ ] call count recorded
- [ ] failure/stop reason recorded

## Tests

- [ ] old tests pass
- [ ] new unit tests pass
- [ ] routing tests pass
- [ ] mocked call-order tests pass
- [ ] 3-race probe passes
- [ ] CoS 6-cycle history probe passes
- [ ] 9 real-match smoke tests pass

---

# 80. Code Agent 最终交付报告

完成后必须返回以下内容。

## A. Research Summary

分别：

```text
SunTzu
HIMA
CoS
```

说明：

```text
source files inspected
core structural invariant
adaptation
removed non-structural components
```

---

## B. Changed Files

分类：

```text
Added
Copied
Modified
```

---

## C. Structure Fidelity

分别给出 ASCII flow：

```text
Original
↓
Our adaptation
```

---

## D. Model Dependency Report

明确写：

```text
Downloaded models: NONE
Local inference servers: NONE
External HIMA advisor service: NONE

All LLM calls:
API_Tools.llm_caller.call_openai_detailed
```

---

## E. Fairness Report

确认：

```text
same decision model
same Strategy Summary
same observation source
same decision interval
same mapper
same scheduler
no knowledge retrieval
no additional SC2 environment access inside one decision
```

---

## F. Test Report

列出执行的：

```bash
python -m compileall ...
python -m pytest ...
python tools/probe_sc2_structural_baselines.py ...
```

以及 9 个 smoke match 的结果。

---

# 81. 参考源码

## SunTzu

Repository:

```text
https://github.com/yorhaha/SunTzu
```

重点：

```text
agents/plan_agent.py
agents/action_agent.py
agents/single_agent.py
players/llm_player.py
players/base_player.py
```

---

## HIMA

Repository:

```text
https://github.com/snumprlab/hima
```

Paper:

```text
Society of Mind Meets Real-Time Strategy:
A Hierarchical Multi-Agent Framework for Strategic Reasoning
COLM 2025
```

重点：

```text
app.py
bot.py
prompt.py
prompts/multi_lm_prompt.py
```

---

## Chain of Summarization

Original Repository:

```text
https://github.com/histmeisah/Large-Language-Models-play-StarCraftII
```

Implementation also available in HIMA repository:

```text
https://github.com/snumprlab/hima
```

重点：

```text
bots/textstarcraft.py
prompts/agent_prompt.py
```

---

# 82. 最终目标结构

实现完成后，当前平台应支持：

```text
naive
plan-execute
self-refine
suntzu
hima
cos
existing knowledge-based modes
```

并且可以用完全相同的 SC2 runtime 比较：

```text
Direct Generation
vs
Planning
vs
Self-Refinement
vs
Hierarchical Self-Correction
vs
Multi-Agent Deliberation
vs
Temporal Context Summarization
vs
Ours
```

---

# 83. 一句话原则

> **只搬 Agent 的“信息如何流动、模型如何分工、结果如何反馈”的结构，不搬原项目的模型、知识、地图脚本或执行器；所有结构最终统一落到当前平台已有的 `{reason, ordered_names}` 与 `ExecutionScheduler` 上。**
