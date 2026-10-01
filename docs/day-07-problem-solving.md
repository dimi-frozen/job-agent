# Day 7 问题复盘：一条证据为什么匹配了全部岗位要求

## 1. 问题是怎样发现的

在 Streamlit 页面使用一份真实的 Agent 系统开发岗位 JD 进行验收时，个人档案中
只有一条已确认的经历：

```text
做过 Java 后端实习，独立实现过 3 个功能；后来学习 Python 和 Agent 开发，
但自述 Java、Python 都不算精通。
```

页面却把这条证据同时用于以下要求：

- 精通主流编程语言。
- HTTP、API、数据库或消息队列。
- 可维护、可扩展的生产级代码。
- DevOps、CI/CD 和自动化运维。
- 权限控制、审计和合规。

最终报告给出了 `ready_to_apply`。这与证据原文明显不符，因此可以确定系统虽然
成功运行，但证据分析逻辑存在错误。

## 2. 原始执行流程

问题出现时的证据路线是：

```text
JobRequirement.evidence_query
    ↓
Chroma 查询最接近的 evidence_id
    ↓
回到 SQLite 加载完整 Evidence
    ↓
检查 Evidence.status
    ↓
confirmed / verified → supported
    ↓
生成 JobAnalysisReport
```

这条路线分别完成了语义检索和来源状态检查，但缺少一个关键问题：

```text
这条真实证据是否真的能够支撑当前这条岗位要求？
```

## 3. 根因

### 3.1 Chroma 的 top-k 只表示相对接近

Chroma 当前查询的是“距离最近的前 3 条”，并不保证返回结果已经足够相关。

当索引里只有一条证据时，无论查询的是 Java、DevOps 还是权限审计，这条证据都
会成为第一名。因此：

```text
排名第一 ≠ 能够支撑结论
```

### 3.2 `confirmed` 被错误理解为“适用于当前要求”

`EvidenceStatus.CONFIRMED` 只表示用户确认这段经历真实存在。

它不能证明：

- 这条证据与当前岗位要求相关。
- 证据达到了岗位要求中的能力程度。
- 一段后端经历自动包含 API、DevOps、权限或审计经验。

正确关系应该是：

```text
证据真实
    +
证据直接适用于当前要求
    ↓
才能支撑报告结论
```

### 3.3 原流程无法识别否定和程度

原文明确包含“两种语言都不算精通”，但向量检索只能发现 Java、Python 等相关
主题，不能稳定理解“不算精通”这一否定关系。

岗位中的“精通”“扎实”“生产级”“复杂工程”等词还包含能力程度，仅凭主题相近
不能证明已经达到对应程度。

## 4. 为什么没有只增加距离阈值

排查时读取了真实 Chroma 距离。结果显示，当前默认 embedding 对中文要求的距离
并不稳定：权限审计查询与这条 Java/Python 经历的距离，甚至比 Java 项目查询更近。

因此只增加一个固定阈值可能产生两类错误：

- 仍然保留语义无关的证据。
- 同时删除真正相关的 Agent 或 Java 证据。

距离仍然适合用来初步缩小候选范围，但不能独立决定证据能否支撑岗位结论。

## 5. 最终解决方案

在 Chroma 初筛和代码证据检查之间增加 `refine_evidence`：

```text
岗位要求
    ↓
Chroma 找到语义相近的候选 evidence_id
    ↓
SQLite 加载完整 Evidence 事实
    ↓
DeepSeek 严格核对证据是否直接支撑对应要求
    ↓
代码校验 requirement_index 和 evidence_id
    ↓
代码执行强程度要求规则
    ↓
check_evidence_node 判断硬性缺口
    ↓
生成报告和投递建议
```

### 5.1 DeepSeek 只做适用性核对

模型收到：

- 岗位要求文本、优先级和 JD 原文。
- Chroma 已经检索到的 evidence ID。
- 证据摘要、来源类型、来源引用和状态。

模型只能从当前要求已有的候选 evidence ID 中选择，不能创建证据，也不能改变证据
状态。

核对规则要求：

- 主题相近不等于能够支撑结论。
- 普通后端经历不能推断出 API、消息队列、DevOps、权限或审计经验。
- 原文存在“不会”“不熟悉”“不算精通”等否定时，不能支撑对应要求。
- 每条岗位要求必须返回一次结果；没有直接证据时返回空列表。

相关实现：

```text
src/job_agent/services/evidence_refinement.py
```

### 5.2 代码继续限制模型输出

模型结果不会被直接信任。程序继续检查：

1. 每个 `requirement_index` 是否恰好出现一次。
2. 是否遗漏岗位要求。
3. 是否重复返回同一个岗位要求索引。
4. 返回的 evidence ID 是否属于 Chroma 为该要求检索到的候选集合。
5. evidence ID 是否能继续对应 SQLite 中的真实证据。

模型返回未知 ID、错误索引或不完整结果时，程序抛出 `ValueError`，不会静默生成
报告。

### 5.3 强程度要求增加确定性规则

包含以下词语的要求具有较强的能力程度：

```text
精通
扎实
生产级
复杂工程
```

即使模型选择了某条证据，代码仍只允许 `verified` 证据支撑这些要求。

这防止一条普通的、仅由对话确认的经历被扩张成“精通语言”或“具备扎实的软件
工程基础”。

### 5.4 防止重复追问同一个缺口

用户可能确认一条真实经历，但严格核对后发现它仍不足以满足岗位要求。

State 新增：

```python
clarified_requirements: list[str]
```

保存候选证据后，Graph 记录本轮已经补充过的岗位要求。重新检索和核对后：

- 已经满足：继续处理其他要求或生成就绪报告。
- 仍不满足：保留为报告缺口，不再反复追问同一项。
- 还有其他未补充的硬性要求：继续询问下一项。

## 6. 修改后的 Graph

```text
START
  ↓
extract_job
  ↓
retrieve_evidence
  ↓
refine_evidence
  ↓
check_evidence
  ├─ 没有硬性缺口
  │      ↓
  │   mark_ready
  │      ↓
  │   build_report
  │      ↓
  │   generate_suggestions
  │      ↓
  │     END
  │
  └─ 存在尚未补充的硬性缺口
         ↓
      ask_for_evidence
         ↓
      draft_candidate
         ↓
      review_candidate
         ├─ 拒绝 → mark_needs_clarification → build_report → END
         │
         └─ 确认 → persist_evidence
                       ↓
                  retrieve_evidence
                       ↓
                  refine_evidence
                       ↓
                  重新检查
```

## 7. 验证结果

### 7.1 离线验收

新增 `scripts/day7_refinement_smoke.py`，覆盖：

- 同一条证据只进入它能够直接支撑的要求。
- `confirmed` 证据不能支撑“精通”等强程度要求。
- 模型返回不存在的 evidence ID 时被拒绝。
- 模型漏项或重复索引时被拒绝。
- 没有候选证据时跳过 DeepSeek 调用。

`scripts/day7_smoke.py` 还增加了：

- 真实经历被确认但仍不足时，生成缺口报告。
- 不重复追问同一条要求。
- 不为缺口报告生成候选简历建议。

Day 5、Day 6 和 Day 7 的相关 smoke 均继续通过。

### 7.2 真实证据核对

使用发现问题时的同一条真实证据，对十条岗位要求重新核对。

最终只保留：

- 使用过 Agent / LLM 相关技术或框架。
- 对 AI 在工程场景中的应用有实践。

以下要求不再被错误标记为已有证据：

- 精通编程语言。
- 扎实的软件工程基础。
- HTTP、API、数据库或消息队列。
- 可维护、可扩展的生产级代码。
- 复杂工程问题分析与解决。
- 内部平台或自动化系统。
- DevOps、CI/CD 或自动化运维。
- 权限控制、审计或合规。

因此所有硬性要求不再自动通过，投递建议也不会继续错误显示为
`ready_to_apply`。

## 8. 当前边界

这次修改解决了“一条证据支持全部要求”的主要错误，但仍有以下边界：

- DeepSeek 的适用性判断仍可能出现误判，因此保留了代码白名单和强程度规则。
- 当前强程度关键词是明确列出的集合，后续可以扩展为能力等级策略。
- Chroma 默认 embedding 对中文的区分能力有限，后续应评估中文 embedding 或
  reranker。
- 目前一次只追问一条硬性缺口，岗位要求很多时交互会较长。

## 9. 这次排查得到的原则

```text
检索到 ≠ 适用
confirmed ≠ 支撑所有结论
语义相近 ≠ 达到要求程度
模型选择 ≠ 可以跳过代码校验
```

一次成功运行只能证明代码路径能够执行。使用真实数据检查结果是否合理，才能发现
系统是否真正完成了业务判断。
