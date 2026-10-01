# Day 6：生成有来源的岗位报告与候选简历建议

目标：把 Day 5 得到的岗位要求与个人证据转换成一份结构化报告，并让 LLM 只根据 `confirmed`、`verified` 证据生成候选简历表述。

今天完成的链路：

```text
JobPosting + list[RequirementEvidence]
                  ↓
          代码规则整理事实
                  ↓
          JobAnalysisReport
          ├─ 每条要求的证据状态
          ├─ 可追溯的 Evidence
          ├─ 缺少的硬性要求
          └─ 规则生成的投递建议
                  ↓
       LLM 生成候选简历表述
                  ↓
       校验引用的 evidence_id
```

Day 6 不让 LLM 决定证据是否可靠，也不生成匹配百分比。程序先确定事实边界，LLM 只在这个边界内组织语言。

## 是否可以进入 Day 6

可以。2026-09-23 验收结果：

- Day 1–5 全部 smoke 通过。
- Day 5 已完成两次中断、确认/拒绝、幂等持久化和重新分析。
- Git 工作区干净，Day 5 已提交为 `7fe44ed`。
- 当前本地 `main` 比 `origin/main` 领先一个提交。

进入 Day 6 前不需要再修改 Day 5。

## 今天要分开的三层职责

### 1. 事实层：代码规则

代码根据 Evidence 状态判断每条岗位要求：

- `supported`：至少存在一条 `confirmed` 或 `verified` 证据。
- `candidate_only`：有 candidate，但没有可靠证据。
- `missing`：没有任何可用证据。

`rejected` 不参与报告。

### 2. 建议层：代码规则

投递建议只根据硬性要求决定：

- 所有 required 都是 `supported`：`ready_to_apply`。
- 任一 required 是 `candidate_only` 或 `missing`：`build_evidence_first`。

preferred 缺失可以展示为提升项，但不阻塞 `ready_to_apply`。

这个建议表示“当前证据覆盖是否足够”，不代表录用概率。

### 3. 表达层：LLM

LLM 可以：

- 把可靠证据改写成简洁的候选简历 bullet。
- 选择更清楚的动作和结果表述。
- 返回它引用的 `evidence_id`。

LLM 不可以：

- 把 candidate 当成已确认事实。
- 自动升级 Capability Level。
- 补充证据中没有出现的数字、结果或技术。
- 修改原始简历文件。
- 决定是否建议投递。

## 三小时安排

| 时间 | 内容 | 验收结果 |
|---|---|---|
| 0:00–0:20 | 复述 Day 5 事实链 | 能解释为什么保存后必须重新检索 |
| 0:20–0:50 | 定义报告领域模型 | 无需 LLM 即可创建完整报告对象 |
| 0:50–1:25 | 编写规则报告服务 | supported、candidate_only、missing 三种状态正确 |
| 1:25–2:00 | 编写简历建议 JSON 服务 | 模型输出转成 Pydantic 候选建议 |
| 2:00–2:30 | 校验证据引用 | 只能引用 confirmed/verified evidence_id |
| 2:30–3:00 | 离线 smoke、一次真实调用和提交 | 无 API key 也能验收，真实输出人工检查 |

## 第 1 步：定义报告领域模型

新建 `src/job_agent/domain/reports.py`。

先定义两个枚举：

```python
class RequirementAssessmentStatus(StrEnum):
    SUPPORTED = "supported"
    CANDIDATE_ONLY = "candidate_only"
    MISSING = "missing"


class ApplicationRecommendation(StrEnum):
    READY_TO_APPLY = "ready_to_apply"
    BUILD_EVIDENCE_FIRST = "build_evidence_first"
```

然后定义三类数据：

```python
class RequirementAssessment(BaseModel):
    requirement: JobRequirement
    status: RequirementAssessmentStatus
    supporting_evidence: list[Evidence]
    candidate_evidence: list[Evidence]


class ResumeSuggestionDraft(BaseModel):
    text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    status: Literal["candidate"] = "candidate"


class JobAnalysisReport(BaseModel):
    job: JobPosting
    assessments: list[RequirementAssessment]
    missing_required: list[JobRequirement]
    recommendation: ApplicationRecommendation
    resume_suggestions: list[ResumeSuggestionDraft] = Field(
        default_factory=list
    )
```

这里保留完整 Evidence，而不只保留 ID，是为了让报告能够展示：

- 证据摘要。
- `source_type`。
- `source_ref`。
- 当前验证状态。

`ResumeSuggestionDraft` 仍然是 candidate。它只是等待用户确认的简历表述，不会覆盖简历，也不会成为新的能力证据。

完成模型后，先手工创建三个对象，验证：

1. `evidence_ids=[]` 会被拒绝。
2. `status="confirmed"` 会被拒绝。
3. `resume_suggestions` 不传值时得到独立的空列表。

## 第 2 步：用普通代码生成事实报告

新建 `src/job_agent/services/job_reporting.py`，实现：

```python
def build_job_analysis_report(
    job: JobPosting,
    matches: list[RequirementEvidence],
) -> JobAnalysisReport:
    ...
```

对每个 `RequirementEvidence`：

1. 忽略 rejected。
2. 把 confirmed、verified 放入 `supporting_evidence`。
3. 把 candidate 放入 `candidate_evidence`。
4. 有 supporting evidence 时状态为 `supported`。
5. 没有 supporting、但有 candidate 时状态为 `candidate_only`。
6. 两者都没有时状态为 `missing`。

只把非 supported 的 required 放进 `missing_required`。

投递建议由 `missing_required` 是否为空决定。不要调用 LLM，也不要生成百分比。

## 第 3 步：让 LLM 只生成候选简历表述

新建 `src/job_agent/services/resume_suggestions.py`，沿用 Day 3、Day 5 的分层：

```text
DeepSeekClient.generate_json()
    ↓ 原始 JSON 字符串
json.loads()
    ↓ Python 字典
Pydantic
    ↓ ResumeSuggestionDraft
evidence_id 白名单校验
```

传给模型的内容只能包括 `supporting_evidence`。Prompt 明确要求：

- 每条建议必须提供至少一个 `evidence_id`。
- 不得引用 candidate 或 rejected。
- 不得添加证据中没有出现的结果、指标和技术。
- 输出只是 candidate 建议。

## 第 4 步：程序校验 LLM 引用

解析模型结果后，收集报告中的可靠证据 ID：

```python
allowed_ids = {
    evidence.id
    for assessment in report.assessments
    for evidence in assessment.supporting_evidence
}
```

每条建议的 `evidence_ids` 必须是 `allowed_ids` 的子集。出现未知 ID、candidate ID 或 rejected ID 时抛出 `ValueError`。

这项校验只能证明“引用来源合法”，不能自动证明自然语言没有夸大，所以建议仍保持 candidate，等待用户审阅。

## 第 5 步：Day 6 离线验收

新增：

```text
scripts/day6_smoke.py
```

至少覆盖：

### 场景 A：required 有 verified 证据

- 状态为 `supported`。
- Evidence 的来源和状态保留。
- 投递建议为 `ready_to_apply`。

### 场景 B：required 只有 candidate

- 状态为 `candidate_only`。
- candidate 不进入 supporting evidence。
- 投递建议为 `build_evidence_first`。

### 场景 C：preferred 没有证据

- 状态为 `missing`。
- 不进入 `missing_required`。
- 不阻塞 `ready_to_apply`。

### 场景 D：LLM 引用非法证据

- 引用不存在的 ID 时拒绝。
- 引用 candidate ID 时拒绝。
- 引用 confirmed/verified ID 时通过。

离线 smoke 使用假的 JSON 客户端，不调用网络。

## Day 6 验收标准

必须满足：

1. Day 1–5 smoke 继续通过。
2. Day 6 smoke 无 API key、无网络也能运行。
3. 每条报告结论能追溯到 Evidence 的来源和状态。
4. candidate 不能支撑岗位要求，也不能进入简历建议白名单。
5. LLM 不能决定投递建议。
6. 不输出未经校准的匹配百分比。
7. 简历建议保持 candidate，不自动修改简历。
8. 你能解释事实报告与 LLM 文案为什么必须分层。

## 今天明确延后

- 把报告节点正式接入 Day 5 交互图。
- Streamlit 输入、暂停与确认界面。
- 直接读取和覆盖真实简历文件。
- 对 Capability Level 自动升级。
- 使用多个真实 JD 做最终演示验收。

这些内容在 Day 7 进行端到端整合。
