# Day 5：加入人工确认，让证据缺口能够暂停、补充并重新分析

目标：当 Day 4 找到缺少可靠证据的硬性要求时，暂停图并向用户追问；把回答整理成候选证据，用户确认后更新能力档案，再用新证据重新分析同一份 JD。

Day 5 最小闭环：

```text
extract_job
    ↓
retrieve_evidence
    ↓
check_evidence
    ├─ 没有缺口 → mark_ready → END
    └─ 存在缺口
          ↓
      ask_for_evidence ── interrupt ①：请用户补充经历
          ↓ resume
      draft_candidate：把回答整理成候选证据
          ↓
      review_candidate ── interrupt ②：请用户确认或拒绝
          ↓ resume
          ├─ 拒绝 → mark_needs_clarification → END
          └─ 确认 → persist_evidence
                         ↓
                  retrieve_evidence → 重新检查
```

今天一次只处理 `missing_required[0]`。如果重新分析后仍有其他缺口，图会再次暂停并询问下一条。多条要求并行追问留到界面稳定后再做。

## 开始前检查

2026-09-20 已重新运行并通过：

- `scripts/day1_smoke.py`
- `scripts/day2_smoke.py`
- `scripts/day3_smoke.py`
- `scripts/day4_minimal_graph.py`
- `scripts/day4_smoke.py`

当前 LangGraph 版本为 `1.2.11`，Git 工作区干净，可以进入 Day 5。

## 今天只增加四个概念

### 1. Checkpointer

Day 4 的图一次运行到底，不需要记住停在哪里。Day 5 会暂停，所以编译时需要：

```python
from langgraph.checkpoint.memory import InMemorySaver

graph = builder.compile(checkpointer=InMemorySaver())
```

`InMemorySaver` 只用于今天的本地学习和离线测试，进程退出后 checkpoint 会消失。它不是 SQLite 业务数据库的替代品：

- checkpointer 保存某个线程运行到哪个节点以及当时的 State；
- 项目 SQLite 保存跨线程都要使用的 Profile、Capability 和 Evidence。

### 2. `thread_id`

每次首次运行和恢复必须传入同一个 ID：

```python
config = {"configurable": {"thread_id": "day5-demo"}}
```

它相当于 checkpoint 的游标。换一个 `thread_id` 就是开始一条新的图执行记录。

### 3. `interrupt()`

节点使用 JSON 可序列化的字典描述“为什么暂停、需要用户回答什么”：

```python
answer = interrupt(
    {
        "kind": "evidence_clarification",
        "question": "请描述你与这项要求有关的真实经历。",
        "requirement": requirement.text,
    }
)
```

默认的 `invoke()` 会把暂停信息放在结果的 `__interrupt__` 中。不要把 Pydantic 对象、数据库连接或函数放进 interrupt payload。

### 4. `Command(resume=...)`

用户回答后，使用同一个 `thread_id` 恢复：

```python
from langgraph.types import Command

result = graph.invoke(
    Command(resume="我在项目中实现过……"),
    config=config,
)
```

resume 值会成为节点中 `interrupt()` 的返回值。

## 一个必须先记住的恢复规则

恢复时，LangGraph 会从发生中断的节点开头重新执行，不是从 `interrupt()` 下一行继续。因此：

1. 一个节点只放一次 `interrupt()`。
2. 不在 `interrupt()` 之前新增 Evidence、追加列表或写外部系统。
3. 用户确认节点和 SQLite 写入节点必须分开。
4. 不使用 `while True` 包住 `interrupt()`；输入无效时，通过条件边重新进入节点。

今天采用两个独立的中断节点，顺序固定：先收集事实，再确认候选证据。

## 三小时安排

| 时间 | 内容 | 验收结果 |
|---|---|---|
| 0:00–0:20 | 运行最小 interrupt 示例 | 能指出首次暂停结果和恢复结果的区别 |
| 0:20–0:45 | 定义候选证据草稿 | 模型输出只能得到 candidate 草稿 |
| 0:45–1:20 | 实现补充与确认节点 | 每个节点只有一次 interrupt，payload 可序列化 |
| 1:20–1:55 | 实现确认后的档案更新 | 确认后才创建或复用 Capability，并保存 confirmed Evidence |
| 1:55–2:25 | 改造图与回环 | 同一 `thread_id` 可以暂停两次并回到检索节点 |
| 2:25–3:00 | 离线 smoke、复述与提交 | 确认、拒绝和重复恢复三个场景均有断言 |

## 第 1 步：运行最小中断示例

运行：

```powershell
.\.venv\Scripts\python.exe -B .\scripts\day5_minimal_interrupt.py
```

然后沿着这条对象路线阅读：

```text
initial_state
  → graph.invoke(initial_state, config)
  → ask_node(state)
  → interrupt(payload)
  → first_result["__interrupt__"][0].value

Command(resume=user_answer)
  → graph.invoke(command, 同一个 config)
  → interrupt() 返回 user_answer
  → ask_node 返回 {"answer": user_answer}
  → final_state
```

开始改项目主图前，先能回答：

1. `InMemorySaver` 保存的是什么，项目 SQLite 保存的又是什么？
2. 为什么恢复时必须继续使用同一个 `thread_id`？
3. `Command(resume=...)` 的值最终去了哪里？
4. 为什么 SQLite 写入不能放在 `interrupt()` 前面？

## 第 2 步：定义候选证据草稿

在 `domain/matching.py` 增加一个只表示“等待确认内容”的模型，例如：

```python
class CandidateEvidenceDraft(BaseModel):
    capability_name: str
    summary: str
    source_quote: str
    status: Literal["candidate"] = "candidate"
```

它不是已入库的 `Evidence`：

- 没有 `capability_id`，因为能力尚未创建或匹配；
- LLM 只能产生 candidate；
- `source_quote` 必须能在用户回答原文中找到；
- 用户确认后，程序才把它转换为 `EvidenceStatus.CONFIRMED` 的 Evidence。

沿用 Day 3 的分层：DeepSeek 客户端只返回原始 JSON，服务层负责 `json.loads()`、Pydantic 校验和 `source_quote in answer` 业务校验。离线 smoke 注入假整理函数，不调用真实 API。

## 第 3 步：扩展 State，但仍只保存业务值

建议新增：

```python
clarification_answer: str
candidate_draft: CandidateEvidenceDraft
candidate_approved: bool
saved_evidence_id: str
```

不要加入：

- `InMemorySaver`
- SQLite connection
- `EvidenceIndex`
- DeepSeekClient
- `thread_id`

`thread_id` 属于运行 config，不是业务 State。数据库与模型客户端仍通过图构建函数注入节点。

## 第 4 步：每个中断单独一个节点

### `ask_for_evidence_node`

读取 `missing_required[0]`，调用一次 `interrupt()`，返回：

```python
{"clarification_answer": answer}
```

### `draft_candidate_node`

读取用户回答和当前缺失要求，调用注入的候选证据整理服务，返回：

```python
{"candidate_draft": draft}
```

### `review_candidate_node`

把草稿转换成普通字典后放进 interrupt payload，恢复值暂时只接受布尔值：

```python
{"candidate_approved": approved}
```

确认和拒绝由普通条件路由处理，不让 LLM 替用户决定。

## 第 5 步：确认后才写入长期档案

新增服务负责：

1. 在当前 Profile 下按规范化名称查找 Capability；
2. 不存在时创建一个 `aware` Capability；
3. 创建 `source_type="conversation"`、`status=confirmed` 的 Evidence；
4. 先写 SQLite，再调用 `EvidenceIndex.upsert()`；
5. 返回保存后的 Evidence。

用户确认一段经历，只能确认“这段事实是用户认可的”，不能自动把能力等级升级成 `independent` 或 `project_verified`。能力升级仍需代码、运行结果或其他更强证据。

写入节点放在确认节点之后。为避免失败恢复时产生重复证据，候选草稿应有稳定 ID，持久化服务在插入前先检查该 ID 是否已经存在。

## 第 6 步：重新检索，而不是手工修改匹配结果

保存成功后，把边连接回 `retrieve_evidence`：

```text
persist_evidence → retrieve_evidence → check_evidence
```

不要直接把新证据 append 到 `requirement_evidence`。重新走 Chroma ID → SQLite Evidence 的路径，才能验证新增证据真的进入了既有事实链路。

## Day 5 离线验收

`scripts/day5_smoke.py` 至少覆盖：

### 场景 A：补充并确认

1. 首次 invoke 在补充问题处暂停；
2. 第一次 resume 后在候选草稿确认处暂停；
3. 第二次 resume 传入 `True`；
4. SQLite 中出现一条 confirmed Evidence；
5. Chroma 能返回它的 ID；
6. 图重新检索后得到 `ready_for_analysis`。

### 场景 B：拒绝候选草稿

1. 第二次 resume 传入 `False`；
2. 不创建 confirmed Evidence；
3. 最终仍为 `needs_clarification`。

### 场景 C：恢复边界

1. 使用不同 `thread_id` 不能接上原来的暂停点；
2. 同一候选草稿重复进入持久化服务不会新增第二条证据；
3. 中断 payload 只包含字典、字符串、列表、布尔值等可序列化数据。

## Day 5 验收标准

必须满足：

1. Day 1–4 smoke 继续通过。
2. Day 5 smoke 不需要 API key 或网络。
3. candidate 草稿不能满足 required 要求。
4. 未确认或已拒绝的草稿不能写成 confirmed Evidence。
5. SQLite 写入只发生在人工确认之后。
6. 保存后必须通过既有检索链重新分析，不能伪造最终状态。
7. 你能解释 checkpoint、长期档案和 Chroma 索引三者的区别。
8. 你能解释节点恢复为什么可能导致重复副作用，以及本项目如何避免。

## 今天明确延后

- 进程重启后继续恢复：后续把 `InMemorySaver` 换成持久化 checkpointer。
- 一次并行追问多条缺失要求。
- 自动提升 `independent` 或 `project_verified` 等级。
- 最终简历改写与投递建议。
- Streamlit 人工确认界面。

