# SC2 Structural Harness Baselines — Plan-and-Execute & Self-Refine 复现实施方案

> **目标仓库**：`https://github.com/ysh020603/SC2-Agent-260510`  
> **目标分支**：`SC2-Agent-knowlegde`  
> **文档用途**：可直接交给 Code Agent 执行。  
> **任务类型**：新增两个 **structure-only / no-knowledge** baseline：  
> 1. `plan-execute`：Plan-and-Execute / Plan-Executor  
> 2. `self-refine`：Self-Refine  
>
> **最高优先级约束**：不重写、不替换、不“顺便重构”现有 `naive`、`data-v2.2`、`data-v2.2-v2`、`data-v2.3` 等实现。  
> 新 baseline 必须以**复制现有独立代码后修改 + 新增独立 package** 的方式实现。对中央路由/CLI 只允许做必要的“追加新 mode”式接入，现有 mode 的行为、默认值和内部实现必须保持不变。

---

## 0. 最终目标

完成后，仓库至少应支持以下两个新增命令：

```powershell
python tools\run_experiment.py `
  --decision-agent-mode plan-execute `
  --decision-model DeepSeek-V4-flash `
  --strategy marine_rush `
  --bot-race terran `
  --enemy-race zerg
```

```powershell
python tools\run_experiment.py `
  --decision-agent-mode self-refine `
  --decision-model DeepSeek-V4-flash `
  --strategy marine_rush `
  --bot-race terran `
  --enemy-race zerg
```

两种新模式必须与现有 `naive` 使用完全相同的：

- Strategy Summary；
- Current Observation；
- previous uncommitted queue；
- race-specific canonical action allowlist；
- decision trigger；
- decision interval；
- canonical mapper；
- `ExecutionScheduler`；
- producer / worker selection；
- SC2 tactical scripts；
- 最终公共输出接口：

```json
{
  "reason": "Concise public explanation.",
  "ordered_names": ["SupplyDepot", "Barracks", "Marine"]
}
```

**唯一主要变量应当是 LLM harness / orchestration structure。**

---

# 1. 强制 Research Gate：在写 Python 代码前完成

Code Agent **不得直接开始写 baseline**。

首先阅读下面的原始论文、官方/作者代码和当前仓库实现，并在仓库中新增研究记录：

```text
docs/structural_baselines/
  PLAN_EXECUTE_REPRODUCTION_NOTES.md
  SELF_REFINE_REPRODUCTION_NOTES.md
```

只有这两个文件完成后，才能开始修改 Python。

---

## 1.1 Plan-and-Execute：必须调研的来源

### A. Plan-and-Solve 原始论文

**Wang et al., ACL 2023**  
*Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning by Large Language Models*

- Paper:
  https://aclanthology.org/2023.acl-long.147/
- Authors' code:
  https://github.com/AGI-Edgerunners/Plan-and-Solve-Prompting

必须确认并记录的核心：

1. 先理解问题并形成 plan；
2. 把完整任务拆分为较小 subtasks；
3. 再按照 plan 执行这些 subtasks；
4. “planning before solving” 是关键，而不是仅仅增加一句 CoT；
5. PS+ 是加入更细致 planning / execution instructions 的增强版。

### B. LangChain 经典 Plan-and-Execute harness

**LangChain, “Plan-and-Execute Agents”, 2023**

- Design article:
  https://www.langchain.com/blog/plan-and-execute-agents
- Main project:
  https://github.com/langchain-ai/langchain

这里作为本项目 **harness 行为定义的主要依据**。

必须确认并记录：

```text
Planner
   ↓
ordered high-level steps
   ↓
for step in steps:
    Executor(step, previous step results)
   ↓
final result
```

经典初版的重要特征：

- higher-level planning 与 shorter-term execution 分离；
- 一个 Planner；
- 一个 Executor；
- 先产生完整 plan；
- 再逐 step 执行；
- previous steps / intermediate results 可以进入后续执行上下文；
- **经典初版只在开头 plan 一次，不在每个 step 重新规划**；
- 相比直接 action agent，会产生更多 LLM calls。

### 本项目的方法身份必须明确

本 baseline 的名字使用：

```text
Plan-and-Execute
CLI: plan-execute
```

不要只复现 Plan-and-Solve 的单 prompt：

```text
"Let's devise a plan and solve step by step."
```

因为那更接近 **prompting baseline**，而不是我们要比较的 **harness baseline**。

本项目应复现的是：

> **LangChain-style Planner → sequential Executor harness**，

同时用 Plan-and-Solve 的原始论文/代码确认“先规划、再按子任务执行”的方法精髓。

---

## 1.2 Self-Refine：必须调研的来源

**Madaan et al., NeurIPS 2023**  
*Self-Refine: Iterative Refinement with Self-Feedback*

- Paper:
  https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html
- Authors' code:
  https://github.com/madaan/self-refine

重点阅读：

```text
README.md
src/acronym/run.py
src/acronym/task_init.py
src/acronym/feedback.py
src/acronym/task_iterate.py
```

必须确认并记录的核心：

```text
Init
  ↓
Initial Output
  ↓
Feedback
  ↓
Iterate / Refine
  ↓
Refined Output
  ↓
if stopping criteria not met:
    Feedback → Refine again
```

原作者代码把任务拆成三类 prompt：

1. `Init`
2. `Feedback`
3. `Iterate`

方法的重要性质：

- generator、feedback provider、refiner 可以是**同一个 LLM**；
- 不要求额外训练；
- 不要求 RL；
- feedback 是显式中间 artifact；
- refinement 是 iterative，而非一次性 rewrite；
- 存在 stopping criterion / max attempts。

### 禁止误实现为 Reflexion

本 baseline **不允许**加入：

- 跨 decision 的 reflection memory；
- 跨 game 的 episodic memory；
- 长期经验积累；
- knowledge retrieval。

否则就不再是纯 Self-Refine，而会混入 Reflexion / memory-based agent 的变量。

---

# 2. 修改前必须审计当前仓库

在修改代码前执行：

```bash
git status --short
git branch --show-current
git rev-parse HEAD
```

记录当前：

- branch；
- commit SHA；
- working tree 状态。

如果 working tree 已有用户未提交修改：

> **不得 reset、checkout、clean、覆盖这些修改。**

继续之前先明确哪些文件是已有用户工作。

然后执行：

```bash
git grep -n -E \
  "decision-agent-mode|SUPPORTED_DECISION_AGENT_MODES|NAIVE_DECISION_AGENT_MODE|data-v2.2|data-v2.3"
```

至少核对这些文件：

```text
SC2_Agent/decision_agent.py
dummies/generic/universal_llm_bot.py
run_vs_ai.py
bot_loader/game_starter.py
tools/run_experiment.py
docs/system-architecture.md
```

还要核对：

```text
API_Tools/llm_caller.py
```

确认当前所有 baseline 最终如何调用 `call_openai_detailed()`，以及返回的：

- content
- raw_content
- reasoning
- model_key
- model
- is_reasoning
- error

等字段。

---

# 3. 不可违反的实验边界

## 3.1 不允许 Knowledge

两个新 baseline 均禁止：

```text
DataSubAgent
knowledge_v2_2
knowledge_v2_2_v2
knowledge_v2_3
query tools
local SC2 structured knowledge dataset
knowledge cache
knowledge ledger
```

代码检查标准：

```bash
git grep -n -E \
  "DataSubAgent|knowledge_v2|query_enemy|query_combat|dataset_store" \
  SC2_Agent/baseline_plan_execute \
  SC2_Agent/baseline_self_refine
```

预期：Python implementation 中应为 **0 个实际依赖**。

文档中提及这些名称用于说明禁止事项可以接受。

---

## 3.2 不允许复用 Ours 的 deterministic planner/auditor

尤其禁止复制或调用 V2 中的：

- deterministic task decomposition；
- horizon resource target；
- combat capability preflight；
- production-throughput assembler；
- gas-capacity planner；
- hard strategic queue auditor；
- weapon-layer response gate；
- dataset-derived prerequisite / counter reasoning。

否则 baseline 就不再是 generic harness comparison。

允许共享的只有**环境接口层**：

- canonical names；
- race prompt context；
- strategy summary；
- observation；
- mapping；
- scheduler；
- LLM caller；
- generic JSON parsing utilities（最好从 naive 复制到 baseline package 内）。

---

## 3.3 一次 decision 内必须冻结 observation

这是最重要的公平性要求之一。

流程必须是：

```text
SC2 at time t
     ↓
capture observation ONCE
     ↓
all Planner / Executor / Feedback / Refine calls
operate on the SAME frozen context
     ↓
one final ordered_names
     ↓
ExecutionScheduler
```

严禁：

```text
Planner
↓
SC2 executes
↓
new observation
↓
Executor
```

也严禁：

```text
Init
↓
execute queue
↓
observe
↓
Feedback
```

因为这样就会把“harness structure”与“额外环境交互频率”混在一起。

---

## 3.4 模型必须相同

在主结构比较中：

```text
Planner       = decision_model_key
Executor      = decision_model_key

Init          = decision_model_key
Feedback      = decision_model_key
Refiner       = decision_model_key
```

不要使用：

```text
data_subagent_model_key
```

也不要给不同角色指定不同模型。

模型的：

- temperature；
- reasoning mode；
- API endpoint；
- max tokens；

均继承当前 `decision_model_key` 对应的同一 API profile。

---

# 4. 代码隔离策略：COPY THEN MODIFY

新增：

```text
SC2_Agent/
├── baseline_plan_execute/
│   ├── __init__.py
│   ├── decision_prompt.py
│   ├── schemas.py
│   ├── planner_prompt.py
│   ├── executor_prompt.py
│   ├── agent.py
│   ├── trace.py
│   ├── README.md
│   └── SOURCE_NOTES.md
│
└── baseline_self_refine/
    ├── __init__.py
    ├── decision_prompt.py
    ├── schemas.py
    ├── init_prompt.py
    ├── feedback_prompt.py
    ├── refine_prompt.py
    ├── agent.py
    ├── trace.py
    ├── README.md
    └── SOURCE_NOTES.md
```

---

## 4.1 必须复制 naive prompt/parser 作为起点

先：

```bash
mkdir -p SC2_Agent/baseline_plan_execute
mkdir -p SC2_Agent/baseline_self_refine

cp SC2_Agent/decision_agent.py \
   SC2_Agent/baseline_plan_execute/decision_prompt.py

cp SC2_Agent/decision_agent.py \
   SC2_Agent/baseline_self_refine/decision_prompt.py
```

然后分别修改**复制件**。

原因：

- 保留与 naive 相同的 SC2 role boundary；
- 保留相同 Strategy Summary；
- 保留相同 observation field guide；
- 保留相同 economy / supply / worker policy；
- 保留相同 canonical allowlist；
- 保留相同 queue replacement semantics；
- 避免新 baseline 偷偷获得更丰富 domain prompt。

### 禁止

不要让新 baseline：

```python
from SC2_Agent.decision_agent import build_decision_messages
```

作为自己的核心 prompt 实现。

应当保留独立复制件，这样以后：

- naive prompt；
- plan-execute prompt；
- self-refine prompt；

可以独立审计，且不会相互修改。

共享纯 utility import 可以保留，例如：

```python
from SC2_Agent.prompt_context import ...
```

---

## 4.2 不要 vendor 第三方完整代码库

不要直接把：

```text
Plan-and-Solve-Prompting/
self-refine/
langchain/
```

复制进本仓库。

这里需要：

> 阅读论文 + 阅读作者实现 → 提炼 algorithmic invariant → 使用本仓库 LLM API 重新实现。

这既能保持仓库干净，也能确保两个 baseline 使用相同 local runtime。

---

# 5. Baseline A：Plan-and-Execute 详细实现

---

## 5.1 SC2 版流程

```text
Frozen Decision Context
(strategy + observation + old queue + allowlist)
                 │
                 ▼
           ┌──────────┐
           │ Planner  │
           └────┬─────┘
                │
       Ordered semantic plan
                │
                ▼
      step 1 → Executor ──┐
      step 2 → Executor ──┤
      step 3 → Executor ──┤
      ...                 │
                          ▼
                Queue fragments
                          │
             deterministic concatenate
                          │
                          ▼
             {reason, ordered_names}
                          │
                          ▼
                Existing mapper
                          │
                          ▼
             ExecutionScheduler
```

---

## 5.2 Planner 的职责

Planner：

- 读取完整 frozen decision context；
- 做 high-level macro decomposition；
- 输出**有顺序的 semantic subtasks**；
- 不直接输出最终 queue；
- 不调用工具；
- 不访问数据库；
- 不读取新 observation；
- 不选择 worker / producer；
- 不执行 SC2 action。

推荐 schema：

```json
{
  "plan_summary": "Prioritize immediate survival, then restore production and economy.",
  "steps": [
    {
      "step_id": 1,
      "objective": "Stabilize the immediate military threat."
    },
    {
      "step_id": 2,
      "objective": "Restore army production capacity."
    },
    {
      "step_id": 3,
      "objective": "Resume economy only after stabilization."
    }
  ]
}
```

约束：

```text
1 <= number of steps <= 4
step_id strictly ordered
```

4-step 上限是 **SC2-specific bounded-compute adaptation**，必须在 `SOURCE_NOTES.md` 中明确，不得伪装成原论文规定。

### Planner 不应输出 hidden CoT

Planner artifact 是公开、简洁的 plan，不要求保存或输出私有 chain-of-thought。

---

## 5.3 Executor 的职责

对每个 planner step：

```text
Executor(
    original frozen context,
    entire plan,
    current step,
    previous executor results,
    current accumulated queue,
    remaining queue capacity
)
```

Executor 负责：

> 把一个 semantic subtask 转换为可执行的 canonical macro queue fragment。

输出：

```json
{
  "step_id": 1,
  "reason": "Add immediately trainable combat units before economic spending.",
  "ordered_names": [
    "Marine",
    "Marine",
    "Marine"
  ]
}
```

注意：

这里的 `ordered_names` 是 **fragment**，不是 public replacement queue。

---

## 5.4 必须 sequential execute

禁止并行：

```text
Planner
├── Executor step 1
├── Executor step 2
└── Executor step 3
```

必须：

```text
Planner
  ↓
Executor step 1
  ↓
result 1
  ↓
Executor step 2 sees result 1
  ↓
result 2
  ↓
Executor step 3 sees result 1 + 2
```

这是 classic Plan-and-Execute 中：

> previous/intermediate execution results influence later step execution

的重要结构特征。

---

## 5.5 不进行 intra-decision re-planning

主 baseline 中：

```text
Planner is called exactly once.
```

即：

```text
plan once
→ execute all steps
```

不要：

```text
plan
→ execute step 1
→ replan
→ execute step 2
```

后者属于 adaptive replanning / closed-loop planner，是另一种 harness。

---

## 5.6 最终 queue 合成

不要额外调用一个 “Finalizer LLM”。

直接：

```python
final_ordered_names = (
    fragment_1
    + fragment_2
    + ...
    + fragment_n
)
```

保留：

- 原始顺序；
- repeated names；
- step 顺序。

不得：

- 自动 deduplicate；
- 自动 reorder；
- 自动插 prerequisite；
- 自动加 supply；
- 自动做 V2-style audit/repair。

Planner/Executor prompt 要告诉模型总 queue 应保持当前项目的近时域规模，通常不超过 20 项。

Executor 每步获得：

```text
current accumulated queue length
remaining recommended capacity
```

如果模型仍导致最终 aggregate 超过 20：

- 视为 orchestration contract violation；
- 本 decision 判 invalid；
- 让现有 runtime 保留 old uncommitted queue；
- trace 中记录 `queue_length_violation`。

不要偷偷截断，以免加入额外 deterministic strategy。

---

## 5.7 最终 public reason

避免为了 `reason` 再多调用一次 LLM。

使用：

```text
plan_summary
```

作为 final public reason。

如果需要，可 deterministic 拼接一个非常短的 executor summary，但不要引入新的 model call。

---

## 5.8 Plan-and-Execute 的调用数

正常：

```text
1 Planner call
+
N Executor calls
```

其中：

```text
1 <= N <= 4
```

因此：

```text
2–5 LLM calls / macro decision
```

必须完整记录。

---

## 5.9 Plan-and-Execute 失败策略

### Planner malformed

```text
result = invalid
old queue remains active
```

### Planner steps = 0 或 > 4

```text
invalid
old queue remains active
```

### 某 Executor malformed

采用 **fail-closed**：

```text
entire new decision invalid
old queue remains active
```

不要只提交 partial fragments。

### Executor step_id mismatch

```text
invalid
```

### Unknown canonical names

仍交给现有公共 canonical mapping 层处理，与 naive 一致。

不要在 baseline 内造第二套 SC2 mapper。

---

# 6. Baseline B：Self-Refine 详细实现

---

## 6.1 SC2 版流程

```text
Frozen Decision Context
         │
         ▼
      ┌──────┐
      │ Init │
      └──┬───┘
         │
  Candidate Queue y0
         │
         ▼
   ┌──────────┐
   │ Feedback │
   └────┬─────┘
        │
  needs_refinement?
    │        │
   no       yes
    │        ▼
    │    ┌────────┐
    │    │ Refine │
    │    └────┬───┘
    │         │
    │       y1
    │         │
    │    Feedback again
    │         │
    └─────────┴────→ final candidate
                        │
                        ▼
             {reason, ordered_names}
                        │
                        ▼
              Existing scheduler
```

---

## 6.2 Init

`Init` 应尽可能接近当前 naive：

```text
same SC2 policy
same strategy summary
same observation
same old queue
same canonical names
```

唯一结构变化：

> 这是 Self-Refine pipeline 的 initial candidate generation。

Init 直接输出完整 replacement queue：

```json
{
  "reason": "Initial macro decision.",
  "ordered_names": [
    "SupplyDepot",
    "Barracks",
    "Marine"
  ]
}
```

这保证：

```text
Self-Refine round 0 ≈ naive-style generation
```

---

## 6.3 Feedback

Feedback 模型读取：

```text
original frozen context
+
current candidate
```

它不生成 replacement queue，只生成**可操作 feedback**。

推荐 schema：

```json
{
  "needs_refinement": true,
  "summary": "The queue over-invests in economy under immediate military pressure.",
  "issues": [
    {
      "issue": "Immediate defense is under-prioritized.",
      "suggestion": "Move currently trainable combat reinforcement ahead of expansion."
    }
  ]
}
```

建议：

```text
0–5 issues
```

Feedback 检查维度只能来自与 naive 相同的公共 decision policy，例如：

- strategy objective consistency；
- observation consistency；
- immediate threat；
- unfinished queue carry-over；
- supply；
- worker saturation；
- resource banking；
- prerequisite awareness；
- canonical vocabulary；
- near-term queue coherence。

### 禁止 Critic 获得额外知识

不能给 Critic：

- knowledge database；
- counter table；
- unit stat table；
- deterministic V2 audit result；
- hidden ground-truth enemy information；
- future game state。

否则 Self-Refine 的提升会混入额外信息。

---

## 6.4 Refine / Iterate

Refiner 输入：

```text
original frozen context
+
current candidate
+
feedback
```

然后输出：

> **完整 replacement queue**

而不是 diff/patch。

格式：

```json
{
  "reason": "Revised macro decision after self-feedback.",
  "ordered_names": [
    "Marine",
    "Marine",
    "SupplyDepot",
    "Barracks"
  ]
}
```

这点非常重要，因为当前 scheduler 的语义本身就是：

```text
new ordered_names completely replaces old uncommitted local queue
```

---

## 6.5 Iterative，而不是一次性 Critique

必须至少支持：

```text
Init
→ Feedback 1
→ Refine 1
→ Feedback 2
→ Refine 2
```

主实验默认：

```python
MAX_REFINE_ROUNDS = 2
```

这意味着：

- 如果 Feedback 1 直接满意：2 calls；
- 如果 refine 一轮后满意：4 calls；
- 如果跑满两轮：5 calls。

定义：

```text
Init = 1 call
Each completed refine round = Feedback + Refine
Final round at max limit does not need an extra post-limit feedback
```

实现时需要确保统计语义明确。

---

## 6.6 停止条件

停止原因必须显式记录：

```text
critic_satisfied
max_refine_rounds
feedback_invalid
refine_invalid
```

### critic_satisfied

若：

```json
{
  "needs_refinement": false
}
```

则立即接受当前 candidate。

### max_refine_rounds

达到：

```text
MAX_REFINE_ROUNDS = 2
```

后接受最后一个 valid candidate。

### feedback_invalid

如果 feedback 无法解析：

- 不继续；
- 接受当前 last valid candidate；
- 记录 stop_reason；
- 不调用额外 repair LLM。

### refine_invalid

如果 refinement 无法解析：

- 不覆盖当前 valid candidate；
- 接受上一版 valid candidate；
- 记录 stop_reason；
- 不增加额外 repair call。

### Init invalid

只有 Init malformed 时：

```text
whole decision invalid
old queue remains active
```

---

## 6.7 不允许 persistent memory

每个 macro decision cycle 都重新：

```text
Init → Feedback → Refine
```

不得把以下内容传给下一次 SC2 decision：

- 上轮 feedback；
- 上轮 critic issue；
- “我上次犯过什么错误”；
- previous reflection memory。

跨 decision 唯一允许存在的是当前系统本来就会提供的：

```text
previous uncommitted canonical names
```

---

# 7. Prompt 设计原则

两个 baseline 的 role prompt 虽然不同，但必须共享当前 naive 的 domain boundary。

---

## 7.1 必须继承 naive 的内容

从复制后的 `decision_prompt.py` 中保留：

1. Agent role and responsibility boundary；
2. Decision lifecycle；
3. queue replacement semantics；
4. race identity/mechanics；
5. economy / production principles；
6. Strategy Objective；
7. Automated Strategy Behaviors；
8. Observation Field Guide；
9. exact canonical action allowlist；
10. near-term horizon；
11. public reason / no hidden CoT requirement。

---

## 7.2 不要让多阶段 baseline 获得更强 SC2 提示词

例如不要只给 Self-Refine Critic 新增：

```text
- compute exact combat counter matrix
- enforce gas budget formula
- calculate production throughput
- identify air/ground weapon layers
```

除非这些内容同样存在于 naive 公共 policy。

否则对比会变成：

```text
harness + extra domain heuristics
vs
naive
```

而不是纯 harness。

---

# 8. 每个 baseline package 的 API

建议统一：

```python
def build_decision_context(**prompt_arguments) -> dict:
    ...
```

返回：

```python
{
    "system_prompt": ...,
    "decision_event": ...,
    "metadata": ...
}
```

以及：

```python
def run_decision(
    *,
    system_prompt: str,
    decision_event: str,
    provider: str,
    log_dir: str | None = None,
    decision_metadata: dict | None = None,
) -> dict:
    ...
```

最终至少返回：

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

这样中央 `UniversalLLMBot` 只负责：

```text
dispatch
→ get final decision
→ shared canonical validation
→ shared mapping
→ shared scheduler
```

---

# 9. Trace / Logging：必须完整记录多阶段调用

新增短目录，避免 Windows 路径过长：

```text
<match>/pe_traces/
<match>/sr_traces/
```

---

## 9.1 Common call record

每个 LLM call 至少记录：

```json
{
  "seq": 1,
  "role": "planner",
  "model_key": "DeepSeek-V4-flash",
  "model": "...",
  "is_reasoning": false,
  "messages": [],
  "content": "...",
  "raw_content": "...",
  "provider_reasoning": "...",
  "reasoning_source": "...",
  "error": "",
  "wall_elapsed_seconds": 1.23,
  "prompt_chars": 12345,
  "output_chars": 812
}
```

不要把 `reason` 当成 chain-of-thought。

Provider reasoning 如果当前 `llm_caller` 已返回，可像现有实现一样单独保存。

---

## 9.2 Plan-and-Execute trace

至少：

```json
{
  "mode": "plan-execute",
  "plan": {...},
  "executor_steps": [
    {
      "step_id": 1,
      "step": {...},
      "input_previous_results": [],
      "output_fragment": [...]
    }
  ],
  "final_decision": {...},
  "model_call_count": 4,
  "status": "completed"
}
```

---

## 9.3 Self-Refine trace

至少：

```json
{
  "mode": "self-refine",
  "initial_candidate": {...},
  "rounds": [
    {
      "round": 1,
      "feedback": {...},
      "refined_candidate": {...}
    }
  ],
  "stop_reason": "critic_satisfied",
  "final_decision": {...},
  "model_call_count": 4,
  "status": "completed"
}
```

---

## 9.4 Token 计数暂不修改 shared caller

当前任务的首要要求是：

> 不动既有基础代码。

因此本次**不要为了 token usage 改写 `API_Tools/llm_caller.py`**。

首版记录：

- model call count；
- wall-clock latency；
- prompt chars；
- output chars；
- model key；
- reasoning mode。

如果论文最终需要 exact prompt/completion tokens：

> 另开一个“uniform instrumentation”任务，统一给所有 mode 加同一种 token-usage 采集。

不要只给新 baseline 加 exact token usage 而给 naive 没有。

---

# 10. 中央接入：只允许 additive integration

---

## 10.1 `dummies/generic/universal_llm_bot.py`

新增：

```python
PLAN_EXECUTE_DECISION_AGENT_MODE = "plan-execute"
SELF_REFINE_DECISION_AGENT_MODE = "self-refine"
```

追加到：

```python
SUPPORTED_DECISION_AGENT_MODES
```

不要改变现有 mode 常量。

在 decision dispatch 中增加两个独立 branch：

```text
plan-execute
self-refine
existing knowledge modes
existing naive
```

### 重要

现有：

```text
knowledge-mode block
naive block
```

尽量保持原样，只包在新的 dispatch 分支中。

不要趁机抽象或重构所有 mode。

---

## 10.2 新 mode 的中央流程

伪代码：

```python
if mode == "plan-execute":
    from SC2_Agent.baseline_plan_execute import (
        build_decision_context,
        run_decision,
    )

    ctx = build_decision_context(**prompt_arguments)

    result = run_decision(
        system_prompt=ctx["system_prompt"],
        decision_event=ctx["decision_event"],
        provider=self.decision_model_key,
        log_dir=... / "pe_traces",
        decision_metadata=ctx["metadata"],
    )

    decision_payload = result["decision"]
    parsed = MacroDecision(...)

    record["baseline_plan_execute"] = {
        "trace_path": result["log_path"],
        "model_call_count": ...,
        "plan_step_count": ...,
        ...
    }
```

Self-Refine 同理。

---

## 10.3 schema version

建议给新的结构 baseline：

```text
schema_version: 5
```

现有：

```text
naive → 2
data-v2.2 → 3
V2 family → 4
```

全部保持不变。

---

## 10.4 `.llm_calls.json`

新 baseline 不能只记录最后一次 subcall。

增加一个**仅供新 baseline 使用**的 helper，例如：

```python
_record_structural_baseline_llm_calls(...)
```

将 `result["llm_calls"]` 逐条写入现有 `_llm_call_records`。

建议 agent role：

```text
plan_execute.planner
plan_execute.executor

self_refine.init
self_refine.feedback
self_refine.refine
```

不要改变现有 mode 的 `_record_llm_call()` 行为。

---

# 11. CLI 接入

只追加 choice，不改默认值。

---

## 11.1 `run_vs_ai.py`

从：

```python
choices=(..., "naive")
```

变为：

```python
choices=(
    ...existing modes...,
    "naive",
    "plan-execute",
    "self-refine",
)
```

保持：

```python
DEFAULT_DECISION_AGENT_MODE
```

完全不变。

---

## 11.2 `bot_loader/game_starter.py`

同样只 append：

```text
plan-execute
self-refine
```

---

## 11.3 `tools/run_experiment.py`

同样 append。

---

## 11.4 全仓检查遗漏 allowlist

再次：

```bash
git grep -n "choices=.*data-v2"
git grep -n "SUPPORTED_DECISION_AGENT_MODES"
git grep -n "decision_agent_mode"
```

对于：

- generic runner；
- batch runner；
- sweep runner；

如果它们本来支持任意 decision mode，则 append 新 mode。

对于只为某个旧方法写的专用 probe：

> 不要为了新 baseline 修改旧 probe。

另建新的 probe。

---

# 12. 新增测试文件，不重写旧测试

建议新增：

```text
tools/tests/test_plan_execute_baseline.py
tools/tests/test_self_refine_baseline.py
tools/tests/test_structural_baseline_routing.py
```

---

# 13. Plan-and-Execute 单元测试

必须覆盖：

### Parser

- valid planner JSON；
- malformed planner JSON；
- 0 steps；
- >4 steps；
- duplicate step ids；
- invalid step order。

### Sequential orchestration

Mock LLM：

```text
Planner
→ Executor 1
→ Executor 2
→ Executor 3
```

assert：

```text
exact call order
```

并验证 Executor 2 能看到 step 1 result。

### Frozen context

每个 call 中：

```text
decision_event / observation
```

必须来自同一个 snapshot。

不得重新调用 observation recorder。

### Queue

测试：

- fragments sequential concatenate；
- repeated canonical names preserved；
- empty fragment valid；
- >20 aggregate → invalid；
- malformed one executor → whole decision invalid；
- no automatic prerequisite/supply insertion。

### No re-plan

一个 decision 中：

```text
Planner call count == 1
```

---

# 14. Self-Refine 单元测试

必须覆盖：

### Init valid

```text
Init → candidate
```

### Critic immediately satisfied

```text
Init → Feedback(false) → stop
```

不得调用 Refine。

### One refinement

```text
Init
→ Feedback(true)
→ Refine
→ Feedback(false)
→ stop
```

### Max two refinement rounds

验证不会进入第三轮 refine。

### Malformed feedback

接受当前 last valid candidate：

```text
stop_reason = feedback_invalid
```

### Malformed refine

回退到 previous valid candidate：

```text
stop_reason = refine_invalid
```

### No persistent memory

连续调用两次 `run_decision()`：

第二次不能自动包含第一次 feedback/history。

### Frozen context

所有 round 使用相同 observation。

---

# 15. Mocked LLM 测试优先于真实 API

测试中 monkeypatch：

```python
call_openai_detailed
```

使用 scripted outputs。

不要用真实 API 来验证 orchestration correctness。

只有：

- parser；
- state transition；
- exact call order；
- trace；
- fallback；

全部通过后，才进入 real model probe。

---

# 16. 新增独立 Probe

不要改旧 knowledge probe。

新增：

```text
tools/probe_structural_baselines.py
```

至少支持：

```bash
python tools/probe_structural_baselines.py \
  --decision-agent-mode plan-execute \
  --model-key DeepSeek-V4-flash
```

以及：

```bash
python tools/probe_structural_baselines.py \
  --decision-agent-mode self-refine \
  --model-key DeepSeek-V4-flash
```

---

## 16.1 三族 directed scenarios

至少覆盖：

### Terran

- high minerals；
- low gas；
- supply pressure；
- military deficit；
- multiple production options。

### Protoss

- air threat；
- insufficient army；
- Gateway / tech transition；
- worker saturation。

### Zerg

- mineral bank；
- larva / supply pressure；
- low gas；
- worker excess；
- mixed enemy threat。

这里的 scenario 只用于测试 harness 能否稳定产出 queue。

**不要把 expected strategic solution 写死进 baseline prompt。**

---

# 17. Real-match smoke test

先每种 race × 每种新 harness 运行 1 局：

```text
3 races × 2 harnesses = 6 matches
```

固定：

- same map；
- same opponent difficulty；
- same game-time limit；
- same model；
- same decision interval；
- same selected strategy family。

检查：

- 不 crash；
- trace 完整；
- final queue 能映射；
- scheduler 正常；
- old modes 没有被影响。

---

# 18. 正式结构比较建议

第一阶段只比较：

```text
naive
plan-execute
self-refine
```

这样最干净。

如果之后加入 “Ours”，必须先再次确认：

> Ours 是否真的完全关闭了 static knowledge / dataset-derived planner information。

当前仓库里叫做 `*-no-knowledge` 的模式，不应仅凭名字就当作“完全无知识结构 baseline”；必须检查其 deterministic planner/auditor 是否仍读取 static dataset。

如果仍读取，就不能在论文中写：

```text
pure harness-only no-knowledge comparison
```

除非另做真正完全 knowledge-free 的 Ours control。

---

# 19. 公平性配置

正式实验必须固定：

| Variable | Requirement |
|---|---|
| Decision model | same |
| Model API profile | same |
| Reasoning mode | same |
| Strategy Summary | same |
| Observation | same |
| Decision interval | same |
| Enemy race/build/difficulty | paired |
| Map | paired |
| Game time limit | same |
| Canonical action space | same |
| Scheduler | same |
| Tactical scripts | same |
| Knowledge tools | disabled |
| External retrieval | disabled |
| Persistent reflection memory | disabled |

---

# 20. 建议报告的实验指标

## Game outcome

- Win；
- Tie；
- Loss；
- score：

```text
Win = 1
Tie = 0.5
Loss = 0
```

---

## Existing SC2 operational metrics

沿用仓库已有统计：

- RUR；
- Average Bank；
- APU；
- game duration；
- supply；
- worker saturation；
- army / combat statistics（若现有记录已提供）。

---

## Harness reliability

新增：

- valid decision rate；
- invalid decision rate；
- accepted queue rate；
- model-call failure rate；
- JSON parse failure；
- average queue length；
- carried / discarded / introduced queue items。

---

## Compute / inference cost

至少：

- mean LLM calls / decision；
- median / mean wall latency；
- prompt chars；
- output chars。

Plan-and-Execute：

- mean planner steps；
- mean executor calls。

Self-Refine：

- mean refinement rounds；
- critic-satisfied-at-round-0 ratio；
- critic-satisfied-after-refine ratio；
- max-round hit ratio。

---

# 21. 现阶段禁止做的事情

Code Agent **不要**：

1. 重写 `SC2_Agent/decision_agent.py`；
2. 把 naive 改成公共 base class；
3. 重构所有 knowledge modes；
4. 修改默认 decision mode；
5. 修改 scheduler；
6. 修改 action mapper；
7. 修改 strategy files；
8. 修改 observation recorder；
9. 给新 baseline 接 DataSubAgent；
10. 给 Critic 接数据库；
11. 给 Plan-Execute 加 adaptive re-planning；
12. 给 Self-Refine 加跨轮 memory；
13. 给 baseline 加 V2-specific deterministic audit；
14. 为了 exact token usage 改 shared LLM caller；
15. 自动删除/覆盖用户已有工作树修改；
16. 直接 vendor 第三方仓库代码。

---

# 22. 实施阶段

---

## Phase 0 — Research & Repository Audit

完成：

```text
docs/structural_baselines/
  PLAN_EXECUTE_REPRODUCTION_NOTES.md
  SELF_REFINE_REPRODUCTION_NOTES.md
```

内容必须分别包含：

```text
paper
official code
core algorithm
what is essential
what is optional
SC2 adaptation
what we intentionally do NOT reproduce
```

然后记录：

```text
target branch
starting commit SHA
existing modified files
```

**Research Gate 通过后才进入 Phase 1。**

---

## Phase 1 — Package Isolation

创建：

```text
SC2_Agent/baseline_plan_execute/
SC2_Agent/baseline_self_refine/
```

复制：

```text
SC2_Agent/decision_agent.py
```

到各自 `decision_prompt.py`。

添加：

```text
README.md
SOURCE_NOTES.md
schemas.py
trace.py
```

先不要接入 runner。

---

## Phase 2 — Plan-and-Execute

依次实现：

```text
planner_prompt.py
executor_prompt.py
schemas.py
agent.py
trace.py
```

先完成 mocked orchestration tests。

验收：

```text
1 planner
N sequential executors
same frozen observation
no knowledge
same model
valid final MacroDecision
```

---

## Phase 3 — Self-Refine

依次实现：

```text
init_prompt.py
feedback_prompt.py
refine_prompt.py
schemas.py
agent.py
trace.py
```

验收：

```text
Init
→ Feedback
→ Refine
→ optional repeat
→ explicit stop
```

同样先通过 mocked tests。

---

## Phase 4 — Central Additive Routing

只在必要文件 append：

```text
plan-execute
self-refine
```

接入：

```text
UniversalLLMBot
run_vs_ai.py
GameStarter
tools/run_experiment.py
```

默认值不变。

---

## Phase 5 — Static Regression

执行：

```bash
python -m compileall SC2_Agent bot_loader dummies/generic tools run_vs_ai.py
```

```bash
python -m pytest tools/tests -q -p no:cacheprovider
```

必须满足：

```text
all pre-existing tests pass
all new tests pass
```

---

## Phase 6 — Structural Probe

运行：

```text
3 races × plan-execute
3 races × self-refine
```

保存 trace。

检查：

- JSON stability；
- mapping；
- call order；
- trace completeness；
- no knowledge access。

---

## Phase 7 — Real Match Smoke

运行 6 局 smoke test。

不要立即做大规模 sweep。

先查看：

```text
crash
invalid queues
timeouts
unexpected call explosion
trace missing
routing error
```

全部正常后再正式 batch。

---

# 23. 最终验收 Checklist

Code Agent 在交付时逐条打勾。

## Preservation

- [ ] `naive` implementation 未修改
- [ ] `data-v2.2` implementation 未修改
- [ ] V2/V2.3 package 内部未修改
- [ ] scheduler 未修改
- [ ] mapper 未修改
- [ ] default mode 未修改
- [ ] old CLI commands 仍可运行

## Plan-and-Execute

- [ ] Planner exactly once per decision
- [ ] Planner outputs ordered semantic plan
- [ ] 1–4 steps
- [ ] Executor sequential
- [ ] later executor sees previous executor results
- [ ] no environment re-observation
- [ ] no replanning
- [ ] no external knowledge
- [ ] same model for Planner/Executor
- [ ] final result is standard `MacroDecision`

## Self-Refine

- [ ] Init produces full candidate
- [ ] Feedback is separate call
- [ ] Refine is separate call
- [ ] iterative loop exists
- [ ] default max refinement rounds = 2
- [ ] explicit stop reason
- [ ] same model for all roles
- [ ] no external knowledge
- [ ] no persistent memory
- [ ] same frozen observation for all rounds

## Logging

- [ ] every subcall traced
- [ ] `pe_traces/` exists
- [ ] `sr_traces/` exists
- [ ] role recorded
- [ ] model key recorded
- [ ] call count recorded
- [ ] latency recorded
- [ ] prompt/output char count recorded
- [ ] public reason separate from provider reasoning

## Tests

- [ ] compileall pass
- [ ] old pytest pass
- [ ] new unit tests pass
- [ ] routing tests pass
- [ ] mocked orchestration tests pass
- [ ] 3-race probes pass
- [ ] real-match smoke tests pass

---

# 24. Code Agent 最终交付内容

完成实现后，Code Agent 必须返回：

## A. Changed files

按：

```text
Added
Modified
Copied-from
```

分类列出。

---

## B. Fidelity report

分别说明：

### Plan-and-Execute

```text
Original mechanism
→ SC2 mapping
→ intentional adaptation
```

### Self-Refine

```text
Original mechanism
→ SC2 mapping
→ intentional adaptation
```

---

## C. Control-variable report

明确确认：

```text
No DataSubAgent
No knowledge database
No V2 planner/auditor
No additional observation access
No persistent memory
Same decision model
Same scheduler
```

---

## D. Test report

列出：

```text
command
pass/fail
```

包括：

```bash
python -m compileall ...
python -m pytest ...
```

以及 probe / smoke commands。

---

## E. Trace examples

各给一个：

```text
Plan-and-Execute decision trace
Self-Refine decision trace
```

说明：

- subcall order；
- final queue；
- stop/failure status。

---

# 25. 方法参考

## Plan-and-Solve / Plan-and-Execute

1. Wang, Lei, et al.  
   **Plan-and-Solve Prompting: Improving Zero-Shot Chain-of-Thought Reasoning by Large Language Models.**  
   ACL 2023.  
   https://aclanthology.org/2023.acl-long.147/

2. Authors' implementation:  
   https://github.com/AGI-Edgerunners/Plan-and-Solve-Prompting

3. LangChain.  
   **Plan-and-Execute Agents.**  
   https://www.langchain.com/blog/plan-and-execute-agents

4. LangChain repository:  
   https://github.com/langchain-ai/langchain

---

## Self-Refine

1. Madaan, Aman, et al.  
   **Self-Refine: Iterative Refinement with Self-Feedback.**  
   NeurIPS 2023.  
   https://proceedings.neurips.cc/paper_files/paper/2023/hash/91edff07232fb1b55a505a9e9f6c0ff3-Abstract-Conference.html

2. Authors' implementation:  
   https://github.com/madaan/self-refine

重点参考：

```text
README.md → General setup
src/acronym/run.py
src/acronym/task_init.py
src/acronym/feedback.py
src/acronym/task_iterate.py
```

---

# 26. 一句话实现原则

> **先忠实复现经典 harness 的控制流，再做最小必要的 SC2 接口适配；所有 domain knowledge、scheduler、observation frequency 和 model configuration 都保持不变。**

最终希望得到的比较是：

```text
Naive
  Direct Generation

vs.

Plan-and-Execute
  Explicit Planning + Sequential Execution

vs.

Self-Refine
  Initial Generation + Iterative Self-Feedback

vs. (future)
Ours
  Proposed Structured Harness
```

而不是：

```text
simple baseline
vs.
baseline + hidden knowledge + extra observation + extra heuristics
```
