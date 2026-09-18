# Day 4：用 LangGraph 串联岗位提取与证据检查

目标：把前三天已经独立运行的岗位提取、证据检索和状态判断串成一张可测试的图。

Day 4 主流程：

```text
START
  ↓
extract_job
  ↓
retrieve_evidence
  ↓
check_evidence
  ├─ required 要求均有可靠证据 → mark_ready → END
  └─ required 要求缺少可靠证据 → mark_needs_clarification → END
```

今天的重点是 State、Node、Edge 各自负责什么。用户追问、`interrupt()`、checkpointer 和能力档案更新留到 Day 5。

## 是否可以进入 Day 4

可以。2026-09-18 重新检查时：

- 工作区干净，Day 3 已提交。
- Day 1、Day 2、Day 3 离线 smoke 全部通过。
- 真实 API 曾在 Day 3 完成记录中验证。
- 岗位模型、DeepSeek 客户端和提取服务已经分层。

三天中断不需要重写 Day 3。先恢复调用链，再增加一个新概念。

## 三小时安排

| 时间      | 内容                     | 验收结果                             |
| --------- | ------------------------ | ------------------------------------ |
| 0:00–0:25 | 恢复 Day 1–3 上下文      | 不看文档说出数据流，并运行三个 smoke |
| 0:25–0:45 | 安装并最小验证 LangGraph | 能解释 State、Node、Edge、compile    |
| 0:45–1:15 | 定义匹配结果与图状态     | State 只保存可序列化业务数据         |
| 1:15–1:50 | 实现要求与证据关联服务   | 每条岗位要求得到一组 SQLite Evidence |
| 1:50–2:30 | 实现节点、路由和图       | 两条条件分支都能到达 END             |
| 2:30–3:00 | 离线验收、复述和提交     | `day4_smoke.py` 通过并建立检查点     |

## 第 0 步：中断后的恢复

先不看文档，尝试用自己的话补完：

```text
Day 1：SQLite 保存用户档案，档案中的能力，以及能力的证据
Day 2：Chroma 返回与jd截取片段语义相近的证据，随后回到证据id，从sqlite里获取对应的证据细节以及能力读取事实
Day 3：JD 字符串 →  → Python 字典 → pydantic对象
```

然后运行：

```powershell
.\.venv\Scripts\python.exe -B .\scripts\day1_smoke.py
.\.venv\Scripts\python.exe -B .\scripts\day2_smoke.py
.\.venv\Scripts\python.exe -B .\scripts\day3_smoke.py
```

如果三项通过且你能解释主链路，就继续。忘记个别语法不算退步；无法说明某个模块的职责时，只复习那个模块。

## 第 1 步：安装 LangGraph，但先运行最小图

在项目依赖中加入稳定的 LangGraph 1.x 版本范围：

```text
langgraph>=1,<2
```

先写一个临时最小例子，确认你理解：

- State 是节点共享的业务数据快照。
- Node 是读取 State 并返回“部分更新”的普通函数。
- Edge 决定下一步执行哪个节点。
- `compile()` 会检查图结构并生成可调用的图。

不要引入 LangChain Agent、工具节点、MessagesState 或 LangSmith。当前项目需要可控工作流，不需要自由规划型 Agent。

## 第 2 步：定义匹配领域对象

新建 `src/job_agent/domain/matching.py`：

```python
class RequirementEvidence(BaseModel):
    requirement: JobRequirement
    evidence: list[Evidence]
```

它表示“一条岗位要求及为它检索到的个人证据”。它不负责判断匹配，也不调用数据库。

证据状态规则：

- `confirmed`、`verified`：可以用于判断要求已有可靠证据。
- `candidate`：可以显示和追问，但不能单独证明已经具备能力。
- `rejected`：不应从索引返回，也不能参与判断。

## 第 3 步：定义图 State

新建 `src/job_agent/agent/state.py`，使用 `TypedDict`：

```python
class JobAnalysisState(TypedDict, total=False):
    profile_id: str
    jd_text: str
    job: JobPosting
    requirement_evidence: list[RequirementEvidence]
    missing_required: list[JobRequirement]
    status: Literal["ready_for_analysis", "needs_clarification"]
```

今天不把以下对象放进 State：

- SQLite connection。
- Chroma client 或 EvidenceIndex。
- DeepSeekClient。
- API key。

这些是运行依赖，不是业务状态，也不应该在未来的 checkpoint 中保存。

今天不为列表字段添加 reducer。每次重新检索时，应使用最新的完整列表覆盖旧列表；如果用追加 reducer，重跑节点可能产生重复证据。

## 第 4 步：实现岗位要求与证据的关联服务

新建 `src/job_agent/services/evidence_matching.py`。它接收：

- `JobPosting`。
- `EvidenceIndex`。
- SQLite connection。

对每个 `JobRequirement`：

1. 使用 `requirement.evidence_query` 查询 Chroma。
2. 得到 `evidence_id` 列表。
3. 逐个调用 `load_evidence()` 回到 SQLite。
4. 忽略已经不存在的 ID。
5. 组装 `RequirementEvidence`。

返回值是与岗位要求顺序一致的 `list[RequirementEvidence]`。

这个服务只负责“关联”，不判断投递、不升级能力，也不生成自然语言结论。

## 第 5 步：实现节点

新建 `src/job_agent/agent/nodes.py`，先实现三个工作节点：

### `extract_job_node`

读取：`jd_text`。

返回：

```python
{"job": job_posting}
```

### `retrieve_evidence_node`

读取：`profile_id`、`job`。

返回：

```python
{"requirement_evidence": matches}
```

### `check_evidence_node`

读取：`requirement_evidence`。

只把下面的要求加入 `missing_required`：

1. `priority` 是 `required`；
2. 没有任何状态为 `confirmed` 或 `verified` 的 Evidence。

缺少 preferred 要求可以记录，但今天不阻塞主流程。

节点必须返回 State 的部分更新，不要复制并返回整个 State。

## 第 6 步：实现条件路由

新建 `src/job_agent/agent/graph.py`：

```text
START
  → extract_job
  → retrieve_evidence
  → check_evidence
  → 条件路由
      ├─ mark_ready
      └─ mark_needs_clarification
```

路由函数只读取 `missing_required`，返回下一个节点名称。它不修改 State。

两个终点节点分别返回：

```python
{"status": "ready_for_analysis"}
```

或：

```python
{"status": "needs_clarification"}
```

然后连接到 `END`。

使用图构建函数接收依赖，避免在模块导入时创建数据库、Chroma 或 DeepSeek 客户端。离线测试可以注入假提取函数和假检索服务。

## 第 7 步：Day 4 离线验收

新建 `scripts/day4_smoke.py`，禁止调用真实 API。至少覆盖三个场景：

### 场景 A：硬性要求有 verified 证据

预期：

```text
status = ready_for_analysis
missing_required = []
```

### 场景 B：硬性要求只有 candidate 证据

预期：

```text
status = needs_clarification
missing_required 包含该要求
```

### 场景 C：只有 preferred 要求缺证据

预期：

```text
status = ready_for_analysis
```

同时检查：

- 图中的岗位对象来自提取节点。
- 检索服务按每条要求的 `evidence_query` 被调用。
- 节点返回的列表没有在重复调用时累积副本。
- Graph 最终到达 END，没有循环。

## Day 4 验收标准

必须满足：

1. Day 1–3 离线 smoke 继续通过。
2. Day 4 三个分支场景通过。
3. 不提供 DeepSeek API key 时，Day 4 smoke 仍能运行。
4. State 中没有数据库连接、客户端或密钥。
5. candidate 证据不会让 required 要求被判定为已满足。
6. 你能画出每个节点读取和写入的 State 字段。
7. 你能解释为什么今天不用 MessagesState、checkpointer 和 `interrupt()`。

## 明确延后

- 真实本地 BGE 与相关度阈值：在真实要求检索质量验收时处理。
- LLM 生成最终匹配分析：证据路由稳定后再加入。
- 用户追问、暂停和恢复：Day 5。
- 更新能力档案并重新分析：Day 5。
- Streamlit：核心循环完成以后。

## 完成后的自检问题

不看代码回答：

1. State、Node 和 Edge 分别负责什么？
2. 为什么节点只返回部分更新？
3. 为什么数据库连接不能放进 State？
4. 为什么 candidate 能被检索，却不能满足 required 要求？
5. 为什么今天的列表字段不需要 reducer？
6. 为什么条件判断由普通代码完成，而不是再调用一次 LLM？

## 完成记录（2026-09-19）

已经完成并验证：

- 安装 LangGraph 1.x，并通过最小计数图理解 State、Node、Edge、`compile()` 和 `invoke()`。
- 定义 `RequirementEvidence`，按岗位要求汇总从 SQLite 加载的候选证据。
- 定义 `JobAnalysisState`，图中只保存业务数据，不保存连接、客户端或密钥。
- 实现岗位要求证据关联服务，过滤不存在及 `rejected` 的证据。
- 实现岗位提取、证据检索和可靠性检查节点，节点只返回部分 State 更新。
- 实现条件路由和两个终点状态。
- 离线验证三种分支：硬性要求有 verified 证据、只有 candidate 证据、加分项没有证据。
- Day 1–3 离线 smoke 继续通过，Day 4 不依赖 API key 或网络。

本日仍按计划延后 `interrupt()`、checkpointer、用户追问和能力档案更新，
这些功能将在 Day 5 的人工确认闭环中处理。
