# SC2 Observation 不返回：根因、修复与验收记录

> 本文是该事故的最终根因与验收摘要。正式批量实验必须遵循
> [`SC2_BATCH_EXPERIMENT_POLICY.md`](SC2_BATCH_EXPERIMENT_POLICY.md)；完整排障时间线已归档至
> [`archive/SC2_HIGH_CONCURRENCY_TIMEOUT_AND_EXIT_INCIDENT.md`](archive/SC2_HIGH_CONCURRENCY_TIMEOUT_AND_EXIT_INCIDENT.md)。

## 1. 现象

Human-Skill Agent 对战内置 SC2 AI 时，部分失败终局会永久等待
`RequestObservation`：

- `SC2_x64` 仍存活，WebSocket 请求已经发出，但没有响应字节；
- SC2 顶层状态仍显示 `in_game`，没有及时返回 `PlayerResult`；
- Python 进程过去可能因为致命传输异常被普通 `except Exception` 吞掉而继续运行；
- runner 因此无法自然结束，整批实验被卡住。

故障主要出现在我方单位接近被完全消灭的阶段。它不是 Qwen 响应慢、服务器
CPU/内存耗尽、并发数过高或一次跨越多个 game loop 导致的。

## 2. 最终根因

`bot_loader/game_starter.py` 原先用子串判断真人玩家：

```python
elif "human" in player1:
    args.real_time = True
```

Human-Skill bot 的注册名是 `universal_llm_human_skill.<race>`，名称中包含
`human`，因此 AI bot 被误判为真人，所有实验被静默切换为 `realtime=True`。

python-sc2 的实时循环会请求一个未来帧：

```python
RequestObservation(game_loop=last_game_loop + game_step)
```

旧版 SC2 Linux 客户端 Base75689 如果在到达目标帧之前进入终局，可能不会返回
目标帧 observation，也不会提前发布终局 `PlayerResult`。这个不可达的未来帧等待
就是 observation 永久 pending 的直接触发条件。

## 3. 修复

### 3.1 修正真人玩家识别

只允许顶层 player key 严格等于 `human` 时启用真人实时模式：

```python
def _is_human_player_spec(player_spec: str) -> bool:
    return player_spec.split(".", 1)[0].strip().lower() == "human"
```

因此：

- `human`、`human.protoss`：真人，`realtime=True`；
- `universal_llm_human_skill.protoss`：bot，保持默认 `realtime=False`。

启动日志同时记录 `realtime`、player spec 和 human 判定，避免模式再次静默漂移。

### 3.2 保留传输故障兜底

- observation 使用独立协议超时；
- 超时后只终止当前对局所属的 SC2 进程，不执行全局 `wineserver -k`；
- timeout/process-exit 继承 `SC2MatchFatalError(BaseException)`，不会被业务层
  `except Exception` 吞掉；
- 单局入口将 match-fatal 转换为退出码 70，让 runner 有界重试；
- Qwen 同步 SDK 调用增加 60 秒 HTTP timeout，避免阻塞 event loop。

### 3.3 被否决的方案

排查中测试过 `RequestSaveReplay + RequestReplayInfo` 终局探针。活体实验发现，
未结束的临时 replay 也可能出现 Tie，因此它会把进行中的对局错误判为终局。
相关代码、环境变量和测试已撤回。胜负只接受正常
`ResponseObservation.player_result`。

## 4. 最终验收

有效批次：

```text
human_skill_sc2_nonrealtime_final_qwen32b_nothinking_1200s_20260810
```

配置：Qwen3-32B non-thinking、`full_v2`、MediumHard、每局最多 1200 游戏秒、
5 runner × 3（总并发 15）。

结果：

- 15/15 启动日志为 `realtime=False`；
- 15/15 首轮完成，全部 return code 0，0 retry、0 failure；
- 14 Defeat、1 Tie，全部来自正常 SC2 observation；
- 0 observation timeout、0 protocol timeout；
- 0 SC2 unexpected exit、0 SIGSEGV、0 match-fatal；
- 0 API/AI-step timeout；
- 339 次 Qwen3-32B 调用，0 reasoning content；
- 15/15 对局产物完整；最慢单局墙钟 741.92 秒；
- 5 个 shard 全部返回 0，验收进程组结束后无残留进程。

自动化测试：241 passed。另有一个修改前已经存在、与本事故无关的 vendored
dataset checksum 失败。Python compile 与 `git diff --check` 均通过。

## 5. 结论与边界

Human-Skill vs 内置 AI 的默认实验路径已经修复：bot 不再被错误送入 realtime
未来帧等待路径，最终压力测试没有再次出现 observation 不返回。

如果调用者明确指定 `--real-time`，Base75689 的原生实时协议缺陷仍可能存在；
此时协议超时、当前对局精确回收、match-fatal 非零退出和有界重试会阻止它永久
挂住整批实验，但不会伪造 Victory/Defeat/Tie。

## 6. 关键位置

- 模式修复：`bot_loader/game_starter.py`
- 协议致命异常：`python-sc2/sc2/protocol.py`
- 单局退出边界：`run_vs_ai_human_skill.py`
- Qwen 请求上限：`SC2_Agent/human_skill_common/agent_base.py`
- 批量运行器：`tools/run_human_skill_ablation_suite.py`
- 完整历史事故时间线：`docs/archive/SC2_HIGH_CONCURRENCY_TIMEOUT_AND_EXIT_INCIDENT.md`
- 现行实验规范：`docs/SC2_BATCH_EXPERIMENT_POLICY.md`
- 最终验收日志：
  `game_records/_human_skill_ablation/human_skill_sc2_nonrealtime_final_qwen32b_nothinking_1200s_20260810/`
