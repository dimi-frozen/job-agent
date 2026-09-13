# Day 3：把原始 JD 变成经过校验的结构化要求

目标：输入一段真实招聘文本，让 DeepSeek 返回 JSON，再使用 Pydantic 将它转换为可靠的岗位对象。今天只建立“模型输出进入程序”的边界，不做最终匹配结论。

主链路：

```text
原始 JD 文本
   ↓
明确的提取 Prompt 与 JSON 示例
   ↓
DeepSeek JSON Output
   ↓
json.loads()
   ↓
Pydantic 校验
   ↓
JobPosting + list[JobRequirement]
```

这里有两层不同的保证：

- JSON Output 尽量保证返回内容是合法 JSON。
- Pydantic 负责检查 JSON 是否符合本项目的数据约定。

合法 JSON 不等于可信业务数据。字段缺失、空要求、错误枚举和不存在于原文的引用仍需要程序检查。

## Day 2 检查结论

已经运行通过：

- `scripts/day1_smoke.py`。
- `scripts/day2_smoke.py`。
- 按 Profile ID 读取全部 Capability 和 Evidence。
- `rejected` 证据从 Chroma 删除。
- `candidate` 证据保留在索引中，并携带原状态。
- 查询结果只返回 `evidence_id`，随后回 SQLite 读取事实。
- 删除索引后可以从 SQLite 重建。

尚未解决、但不阻塞 Day 3：

- Day 2 使用可预测的测试向量，尚未验证本地 BGE 的真实中文语义质量。
- 当前查询只有 `top-k`，没有相似度阈值；不相关查询也可能返回现有证据。
- `scripts/day2_smoke.py` 的 candidate 断言尚未提交。

前两项会在岗位要求与证据检索正式连接时处理。今天不把 Embedding、LLM 和业务判断三个变量同时混在一起。

## 三小时安排

| 时间 | 内容 | 验收结果 |
|---|---|---|
| 0:00–0:15 | 收尾 Day 2 | 两个 smoke 通过，提交 candidate 断言 |
| 0:15–0:45 | 定义岗位模型 | 无需 LLM 即可创建并校验岗位对象 |
| 0:45–1:20 | 编写纯 JSON 解析 | 有效、无效和缺字段 JSON 都有明确结果 |
| 1:20–2:00 | 建立 DeepSeek JSON 客户端 | 密钥从环境读取，能拿到原始 JSON 字符串 |
| 2:00–2:35 | 编写 JD 提取服务 | 一段真实 JD 能转成 Pydantic 对象 |
| 2:35–3:00 | 离线验收、一次真实调用、解释与提交 | `day3_smoke.py` 通过，真实样本人工核对 |

## 第 0 步：收尾 Day 2

1. 运行 Day 1 和 Day 2 smoke。
2. 查看 `scripts/day2_smoke.py` 中新增的三行断言，解释为什么 candidate 可以被检索，却不能直接支撑结论。
3. 只暂存 Day 2 相关文件，检查暂存内容后提交。

不要把无关的编辑器设置自动混入提交。

## 第 1 步：定义岗位领域模型

新建 `src/job_agent/domain/jobs.py`。建议先实现：

```python
class RequirementPriority(StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"


class JobRequirement(BaseModel):
    text: str
    priority: RequirementPriority
    source_quote: str
    evidence_query: str


class JobPosting(BaseModel):
    title: str | None = None
    company: str | None = None
    requirements: list[JobRequirement]
```

字段职责：

- `text`：规范化后的岗位要求，供后续判断与展示。
- `priority`：区分硬性要求和加分项。
- `source_quote`：JD 原文依据，防止分析失去来源。
- `evidence_query`：用于查询个人能力证据的简短语句。
- `requirements`：至少包含一项，不能接受空列表。

先用普通 Python 数据创建对象，确认默认值、枚举和非空校验，再接模型。

## 第 2 步：先写纯解析函数

在 `src/job_agent/services/job_extraction.py` 中先实现一个不调用网络的函数：

```python
def parse_job_extraction(raw_json: str, source_text: str) -> JobPosting:
    ...
```

执行顺序：

1. `json.loads(raw_json)` 将字符串转为 Python 字典。
2. `JobPosting.model_validate(data)` 检查结构和类型。
3. 检查每条 `source_quote` 能否在原始 JD 中找到。
4. 返回经过校验的 `JobPosting`。

这里必须区分三类失败：

- 不是合法 JSON：`json.JSONDecodeError`。
- JSON 合法但字段不符合模型：`pydantic.ValidationError`。
- 字段结构正确，但引用并非来自原 JD：抛出有明确消息的业务错误。

先把这一步写通，后面即使更换模型供应商，业务校验也不会变化。

## 第 3 步：建立最小模型客户端

新建 `src/job_agent/llm/client.py`。第一版只承担：

1. 从环境变量读取 API key、base URL 和 model。
2. 接收 system 与 user 消息。
3. 请求 JSON Output。
4. 返回模型生成的原始字符串。
5. 空内容或请求失败时抛出明确异常。

环境变量建议使用：

```text
DEEPSEEK_API_KEY
DEEPSEEK_BASE_URL
DEEPSEEK_MODEL
```

不要把真实密钥写入 Python、README、测试或 Git。客户端不负责 `JobPosting` 校验，也不导入 SQLite、Chroma 或 LangGraph。

这次可以使用 OpenAI Python SDK 连接 DeepSeek 的兼容接口。沿用你已经理解的 messages 结构，但不要直接复制旧项目的全套流式与工具调用代码。

## 第 4 步：编写 JD 提取服务

继续在 `services/job_extraction.py` 中实现：

```python
def extract_job_posting(jd_text: str, client: ...) -> JobPosting:
    ...
```

它只做三件事：

1. 构造要求模型输出 JSON 的 prompt，并给出一份简短 JSON 示例。
2. 调用客户端取得原始 JSON 字符串。
3. 调用 `parse_job_extraction()` 返回 Pydantic 对象。

Prompt 必须明确：

- 不能补充原文没有的要求。
- `source_quote` 必须复制原文中的短句。
- `evidence_query` 描述需要从个人档案中寻找哪类事实。
- 无法确定公司或岗位名称时返回 `null`。

今天不让模型决定“投不投”，也不让它直接修改能力档案。

## 第 5 步：离线与在线分开验收

新建 `scripts/day3_smoke.py`，默认不访问网络。使用固定的原始 JD 和固定 JSON 检查：

1. 正确 JSON 可以得到 JobPosting。
2. `requirements=[]` 会校验失败。
3. 空 `text`、`source_quote` 或 `evidence_query` 会校验失败。
4. 错误枚举值会校验失败。
5. `source_quote` 不在 JD 原文中会失败。
6. 中文字段保持不变。

离线 smoke 通过后，再用一个单独入口做一次真实 API 调用。人工逐条对照真实 JD，检查有没有遗漏、误判硬性要求或伪造引用。真实 API 不进入自动 smoke，避免测试依赖网络、余额和模型波动。

## Day 3 验收标准

必须满足：

1. 一段真实 JD 能稳定转换成 `JobPosting`。
2. 每条要求都有可回查的 `source_quote`。
3. 模型返回错误结构时，错误停在清楚的边界，不会写入数据库。
4. 不提供 API key 时，离线 smoke 仍能运行。
5. 日志和报错不输出 API key。
6. 你能解释 JSON、Python 字典和 Pydantic 对象是三个不同阶段。

## 提前完成时的加餐

只解析一小段简历项目描述，输出候选证据草稿：

```text
capability_name
summary
source_quote
suggested_level
```

这一步只生成草稿，不创建 Capability、不写 SQLite，也不升级能力等级。完整简历导入留到结构化输出边界稳定之后。

## 完成后的自检问题

不看代码回答：

1. JSON Output 已经保证合法 JSON，为什么还需要 Pydantic？
2. 为什么 `source_quote` 必须能在原始 JD 中找到？
3. 为什么模型客户端不应该直接返回 JobPosting？
4. 为什么自动 smoke 不调用真实 API？
5. 如果模型返回空字符串，错误应该在哪一层处理？

## 完成记录（2026-09-14）

已经完成并验证：

- 定义 `JobPosting`、`JobRequirement` 和岗位要求优先级。
- 将 JSON 字符串依次转换为 Python 字典和 Pydantic 对象。
- 拒绝空要求、空字段、错误枚举和无法回查原文的 `source_quote`。
- 使用假的客户端完成离线验收，不依赖 API key 或网络。
- 使用真实 DeepSeek API 完成一次岗位提取，并通过 Pydantic 与原文检查。
- `.env` 已被 Git 忽略，`.env.example` 不包含真实密钥。

本次官方端点的实际错误响应显示 Flash 模型标识为 `deepseek-flash`，
因此项目使用该运行时可接受的名称，而不是界面显示名称。
