# Day 2：从完整档案到第一条可追溯检索

目标：从一个 `Profile` 出发取出它的全部能力和证据，将证据建立为 Chroma 索引；查询后拿到 `evidence_id`，再回到 SQLite 读取真实记录。

今天完成的主链路是：

```text
Profile ID
   ↓
SQLite：读取能力和证据
   ↓
Chroma：建立可重建索引
   ↓
自然语言查询
   ↓
evidence_id
   ↓
SQLite：读取证据原文、来源和验证状态
```

今天不接入 LLM、LangGraph、Streamlit，也不自动解析整份简历。自动把简历转为候选证据需要 LLM 结构化输出，移动到 Day 3；否则今天会同时学习数据库关系、向量库和模型调用，无法吃透边界。

## Day 1 检查结论

已经实测通过：

- `CapabilityLevel`、`EvidenceStatus` 的枚举契约。
- `Profile`、`Capability`、`Evidence` 的字段契约。
- UUID、UTC 时间和空列表由 `default_factory` 独立生成。
- Profile、Capability、Evidence 可以写入 SQLite 并无损读回。
- 外键约束有效；读取不存在的记录会返回 `None`。
- 中文列表经过 JSON 保存后可以正确恢复。

Day 2 开始前补三个缺口：

1. `Profile.name` 和 `Evidence.summary` 目前仍接受空字符串，与 Day 1 的“不能为空”约定不一致。
2. `scripts/day1_smoke.py` 只检查枚举和字段，没有自动执行 SQLite 往返与外键检查。
3. Day 1 代码尚未提交；补完并验证后，先建立 Day 1 Git 检查点，再开始 Chroma。

完成这三项后，Day 1 才算完整收口。

## 三小时安排

| 时间 | 内容 | 验收结果 |
|---|---|---|
| 0:00–0:25 | 收口 Day 1 | 校验与数据库自动验收通过，并建立 Day 1 Git 检查点 |
| 0:25–1:05 | 多行关联查询 | 能按 `profile_id` 读取能力，按 `capability_id` 读取证据 |
| 1:05–1:30 | 汇总档案证据 | 能从一个 Profile ID 得到全部 Evidence |
| 1:30–1:50 | 理解并安装 Chroma | 能说明 SQLite 与 Chroma 各自负责什么 |
| 1:50–2:40 | 建立并查询证据索引 | 自然语言查询返回相关 `evidence_id` |
| 2:40–3:00 | 验收、解释、提交 | 完成 Day 2 脚本并建立 Git 检查点 |

## 第 0 步：收口 Day 1

### 非空字符串

先让下面两种输入触发 Pydantic 校验错误：

```python
Profile(name="")
Evidence(capability_id="c1", source_type="code", summary="")
```

先只处理真正的空字符串。全空格、统一去除首尾空格等规则可以以后集中设计，今天不扩展范围。

### 扩展自动验收

让 `scripts/day1_smoke.py` 除了字段契约，还使用临时数据库检查：

1. 初始化三张表。
2. 创建并保存 Profile、Capability、Evidence。
3. 分别读回三个对象并比较。
4. 保存一个引用不存在 Profile 的 Capability，确认触发 `sqlite3.IntegrityError`。

测试数据必须写入临时目录，不能污染项目的 `data/`。

## 第 1 步：从单条读取变为关联列表

在 `storage/sqlite.py` 中增加：

```python
def list_capabilities_by_profile(
    connection: sqlite3.Connection,
    profile_id: str,
) -> list[Capability]:
    ...


def list_evidence_by_capability(
    connection: sqlite3.Connection,
    capability_id: str,
) -> list[Evidence]:
    ...
```

需要理解的变化：

```sql
-- 单条读取：根据对象自己的主键查找
WHERE id = ?

-- 关联读取：根据外键查找属于父对象的多条记录
WHERE profile_id = ?
WHERE capability_id = ?
```

单条查询使用 `fetchone()`，多条查询使用 `fetchall()`。没有关联记录时返回 `[]`，这是有效业务结果。

## 第 2 步：从 Profile 得到全部证据

先用普通 Python 函数组合前面的查询，不新增复杂领域模型：

```python
def list_evidence_by_profile(
    connection: sqlite3.Connection,
    profile_id: str,
) -> list[Evidence]:
    ...
```

执行顺序应该由你自己写出来并解释：

1. 根据 `profile_id` 找到全部 Capability。
2. 对每项 Capability，根据 `capability.id` 找到 Evidence。
3. 将多个证据列表合并为一个扁平的 `list[Evidence]`。

这一段会复用你在 `build_chunks()` 中学过的“多个列表汇总为一个扁平列表”的思路。

## 第 3 步：明确 SQLite 与 Chroma 的边界

SQLite 是事实来源，Chroma 只是可重建索引：

| 内容 | SQLite | Chroma |
|---|---:|---:|
| 完整 Evidence | 是 | 否 |
| `evidence_id` | 是 | 是 |
| 用于语义搜索的文本 | 可保存 | 是 |
| 来源和验证状态 | 是 | 只保存检索所需 metadata |
| 能否单独恢复业务数据 | 是 | 否 |

索引规则：

- `rejected` 证据不进入索引。
- 其他状态可以进入索引，但必须把 `status` 保存为 metadata。
- 后续生成岗位结论时，`candidate` 只能提示“可能存在相关经历”，不能直接证明能力。

## 第 4 步：建立最小 Chroma 适配器

新建 `src/job_agent/rag/evidence_index.py`，只实现三个职责：

1. 把 Evidence 转成索引文本和 metadata。
2. 写入或更新一条证据索引。
3. 接收查询文本，返回相关 `evidence_id` 列表。

Chroma 返回的文本不是最终事实。查询得到 ID 后，必须调用 `load_evidence()` 回到 SQLite 读取当前记录。这能避免索引中的旧 metadata 成为业务真相。

第一版不要添加通用向量库基类、多个 embedding provider 或异步接口。

## Day 2 验收场景

准备一份档案：

```text
Profile：张先生，目标岗位 AI 应用开发
  ├─ Capability：RAG
  │    ├─ Evidence：实现文档切块与向量检索，verified
  │    └─ Evidence：学习重排模型，candidate
  └─ Capability：LangGraph
       └─ Evidence：实现状态图和条件路由，confirmed
```

验收必须满足：

1. 只提供 Profile ID，可以读到两项能力和三条证据。
2. 查询“是否做过 Agent 工作流”时，优先返回 LangGraph 证据的 ID。
3. 根据 ID 从 SQLite 读回原文、来源和状态。
4. 查询不存在的方向时允许低相关或空结果，调用方不能伪造证据。
5. 删除 Chroma 测试目录后，可以从 SQLite 重建索引。
6. `scripts/day1_smoke.py` 与新的 `scripts/day2_smoke.py` 都通过。

## 完成后的自检问题

不看文档回答：

1. 为什么不能只使用 Chroma 保存证据？
2. `fetchone()` 和 `fetchall()` 对应什么业务关系？
3. 为什么 Chroma 查询结果要再次回到 SQLite？
4. `candidate` 证据为什么可以被检索，却不能直接支撑简历结论？
5. Chroma 目录丢失后，系统凭什么能够重建？

答不清的问题就是下一次复习入口，不要靠背代码掩盖。
