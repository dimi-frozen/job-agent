# Day 7：整合完整工作流并做最小可演示界面

真实页面验收发现并修复的证据误匹配问题，见
[Day 7 问题复盘](day-07-problem-solving.md)。

目标：把 Day 3–6 的独立能力连接成一条端到端工作流，并通过最小 Streamlit 页面完成真实演示。

Day 7 最终链路：

```text
输入文本 JD
    ↓
提取岗位要求
    ↓
从 Chroma 找 evidence_id，再回 SQLite 读取事实
    ↓
严格核对证据是否直接支撑每条岗位要求
    ↓
检查硬性证据
    ├─ 证据不足
    │    ↓
    │  追问用户 → 候选证据 → 用户确认
    │    ↓
    │  写入 SQLite 和 Chroma → 重新检索
    │
    └─ 证据充分
         ↓
      生成事实报告
         ↓
      生成有 evidence_id 引用的候选简历建议
         ↓
      页面展示结果
```

今天不再增加新的业务概念。主要工作是连接、驱动和验收已有模块。

## 是否可以进入 Day 7

可以。2026-10-01 重新验收时：

- Day 1–6 的全部离线 smoke 均通过。
- Day 6 报告模型、规则报告、可靠证据白名单和无证据跳过 LLM 均通过。
- Day 6 已提交为 `1a38bc4`。
- Git 工作区在建立 Day 7 计划前干净。

一周中断不要求重写 Day 6。先恢复完整数据流，再开始整合。

## 今天的必须项与展示项

### 必须完成

1. 把 `JobAnalysisReport` 放进图 State。
2. 把事实报告节点接到 Day 5 交互图末端。
3. 在 Chroma 初筛后严格核对证据与岗位要求的适用关系。
4. 只在存在可靠证据时生成候选简历建议。
5. 使用 `day7_smoke.py` 离线跑通确认、拒绝和直接就绪三条路线。
6. 确保最终报告来自重新检索后的证据，而不是直接拼接用户回答。

### 完成核心验收后加入

1. 最小 Streamlit 页面。
2. 两份真实 JD 演示。
3. README 运行说明与项目讲解提纲。

如果界面调试超时，优先保留完整离线闭环。Streamlit 是展示层，不能代替业务验收。

## 三小时安排

| 时间 | 内容 | 验收结果 |
|---|---|---|
| 0:00–0:20 | 恢复 Day 3–6 主链路 | 能从 JD 一直说到候选简历建议 |
| 0:20–0:55 | 增加报告与建议节点 | 节点只返回 State 的部分更新 |
| 0:55–1:30 | 把节点接入完整图 | ready、确认、拒绝三条路线都能结束 |
| 1:30–2:00 | 编写 `day7_smoke.py` | 无网络完成端到端验收 |
| 2:00–2:40 | 建立最小 Streamlit 页面 | 页面能驱动首次运行和两次 resume |
| 2:40–3:00 | 两份真实 JD、文档与提交 | 能演示、能解释、Git 有检查点 |

## 第 0 步：先复述完整对象路线

不看文档补全：

```text
JD 字符串
→ __________
→ JobPosting
→ __________
→ list[RequirementEvidence]
→ check_evidence_node
→ interrupt / ready
→ __________
→ JobAnalysisReport
→ __________
→ list[ResumeSuggestionDraft]
```

参考答案中的关键对象应该包括：

- `extract_job_posting`
- `match_job_requirements`
- `persist_confirmed_evidence`
- `build_job_analysis_report`
- `generate_resume_suggestions`

## 第 1 步：扩展 State

在 `JobAnalysisState` 增加：

```python
analysis_report: JobAnalysisReport
```

不把 Streamlit 的组件值、数据库连接或 LLM 客户端放进 State。

图 State 保存业务执行结果；Streamlit Session State 只负责页面多次重跑之间保留 UI 驱动状态。

## 第 2 步：新增两个节点

在 `agent/nodes.py` 增加 callable 类型：

```python
BuildReport = Callable[
    [JobPosting, list[RequirementEvidence]],
    JobAnalysisReport,
]

GenerateSuggestions = Callable[
    [JobAnalysisReport],
    list[ResumeSuggestionDraft],
]
```

### `build_report_node`

读取：

- `job`
- `requirement_evidence`

返回：

```python
{"analysis_report": report}
```

### `generate_suggestions_node`

读取 `analysis_report`，生成候选建议后使用 Pydantic 的复制更新：

```python
updated_report = report.model_copy(
    update={"resume_suggestions": suggestions}
)
return {"analysis_report": updated_report}
```

不要在节点中原地修改 State 中已有的 Pydantic 对象。

## 第 3 步：构建完整图

保留现有 `build_job_analysis_graph()` 和 `build_interactive_job_analysis_graph()`，避免 Day 4、Day 5 调用方式失效。

新增：

```python
build_complete_job_analysis_graph(...)
```

完整图的后半段：

```text
check_evidence
  ├─ 有缺口 → ask_for_evidence → draft → review
  │                                      ├─ 拒绝
  │                                      │    ↓
  │                                      │ mark_needs_clarification
  │                                      │    ↓
  │                                      │ build_report → END
  │                                      │
  │                                      └─ 确认 → persist → retrieve → check
  │
  └─ 无缺口 → mark_ready
                   ↓
              build_report
                   ↓
           generate_suggestions
                   ↓
                  END
```

实际页面验收发现，Chroma 的最近邻查询只负责找候选项；当索引中只有一条
证据时，即使语义无关，它仍可能成为第一名。因此完整图在
`retrieve_evidence` 和 `check_evidence` 之间增加 `refine_evidence`：

```text
retrieve_evidence
    ↓
refine_evidence
    ↓
check_evidence
```

`confirmed`、`verified` 表示证据本身的来源状态，不能证明它自动适用于所有
岗位要求。严格核对只允许从 Chroma 已返回的 evidence ID 中选择；代码继续
检查模型没有创建新 ID、漏掉要求或返回重复索引。包含“精通”“扎实”
“生产级”“复杂工程”的强程度要求只能由 `verified` 证据支撑。

拒绝分支仍然生成缺口报告，但不生成简历建议。ready 分支才进入候选简历建议节点。

可以抽取内部 builder 减少 Day 5 与 Day 7 的节点注册重复，但不要为了去掉少量重复代码改变已经验证的业务行为。

## 第 4 步：Day 7 离线端到端验收

新增 `scripts/day7_smoke.py`，所有 LLM 和 embedding 使用假依赖。

### 场景 A：现有证据已经充分

- 不触发 interrupt。
- 得到 `ready_for_analysis`。
- 报告包含可靠 Evidence。
- 简历建议引用合法 evidence ID。

### 场景 B：缺证据后补充并确认

- 首次暂停收集回答。
- 第二次暂停确认 candidate 草稿。
- 确认后写入并重新检索。
- 最终报告引用重新从 SQLite 加载的 confirmed Evidence。
- 简历建议只引用该 Evidence ID。

### 场景 C：拒绝候选证据

- 不写 SQLite 和 Chroma。
- 最终状态为 `needs_clarification`。
- 报告保留 required 缺口。
- 不调用候选简历建议生成服务。

Day 7 smoke 必须断言调用次数，防止 graph 回环导致模型或持久化服务重复执行。

## 第 5 步：建立最小 Streamlit 页面

在 `pyproject.toml` 增加：

```text
streamlit>=1.40,<2
```

建议入口：

```text
app.py
```

页面只保留四块：

1. Profile 与 JD 输入。
2. 当前 interrupt 问题。
3. candidate 草稿确认或拒绝。
4. 最终岗位报告和候选简历建议。

Streamlit 每次交互会从头执行脚本，因此使用 `st.session_state` 保存：

- 当前 `thread_id`。
- 已编译的 graph。
- 最近一次 graph result。
- 当前页面阶段。

不要使用 Session State 保存长期业务事实；刷新页面可能结束 WebSocket 会话，而 Profile、Capability 和 Evidence 必须继续由 SQLite 保存。

JD 输入、补充回答和候选确认分别放在独立 form 中。点击 submit 后再调用 `graph.invoke()`，避免输入一个字符就触发一次模型调用。

运行：

```powershell
.\.venv\Scripts\streamlit.exe run .\app.py
```

## 第 6 步：真实演示验收

至少选择两份与你目标岗位相关的真实文本 JD：

1. 一份已有较充分证据，直接生成报告。
2. 一份包含当前证据缺口，完整走过追问、确认和重新分析。

人工检查：

- JD 要求没有被模型虚构。
- source quote 能回到 JD 原文。
- 报告中的 Evidence 能回到 SQLite 来源。
- 候选简历建议没有新增数字和结果。
- candidate 建议清楚标记为待审核。

不要为了让演示结果好看而确认没有真实做过的经历。

## Day 7 验收标准

必须满足：

1. Day 1–6 smoke 继续通过。
2. `day7_smoke.py` 无网络通过三条完整路线。
3. 报告和简历建议已经接入 LangGraph，而不是由界面临时拼接。
4. Chroma 返回的候选证据经过严格适用性核对后才进入报告规则。
5. Streamlit 只调用业务层，不复制证据判断规则。
6. 页面 rerun 后，同一会话仍使用原 `thread_id` 和 graph。
7. SQLite 仍是业务事实来源，Chroma 仍只返回候选 ID。
8. 两份真实 JD 的结果经过人工核对。
9. 项目中没有 API key、真实隐私数据或生成缓存被提交。
10. 你能在不看文档时演示并解释整个闭环。

## Day 7 完成后再评估的增强项

- 使用持久化 checkpointer，让进程重启后继续中断。
- 保存历史岗位、分析报告与投递状态。
- 读取现有简历并生成差异预览。
- 真实中文 embedding 模型和相关度阈值。
- 多用户隔离和 profile 级 Chroma 过滤。
- 部署与公开演示地址。
