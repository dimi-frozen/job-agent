# Day 1：核心数据模型与 SQLite

目标：能够创建一份个人档案，为它添加能力和证据，并从 SQLite 读回相同内容。

## 学习方式

你不需要在没接触过这些概念时，直接独立写完整文件。我们按下面的循环学习：

```text
先运行并观察报错 -> 一次只学一个概念 -> 跟着示例写几行
        -> 立即运行验证 -> 用自己的话解释 -> 再进入下一个概念
```

遇到不懂时，先停在当前小节，不要同时搜索和补完后面的代码。学习目标不是“第一次就能默写”，而是：

1. 能说出这几行代码负责什么。
2. 能看懂每个值从哪里来、会存到哪里。
3. 改一个值后，能预测运行结果。
4. 最后才是不看示例独立写一遍。

## 分段练习

### 第 0 步：只观察，不写代码

运行 `python scripts/day1_smoke.py`，阅读第一条失败信息。当前失败是正常的，它只是告诉我们第一个还没完成的约定。

### 第 1 步：只学习 `CapabilityLevel`

先只理解下面三个问题：

- `class CapabilityLevel(StrEnum)` 为什么叫“枚举”？
- 成员名和字符串值分别有什么作用？
- 为什么数据库更适合保存 `"aware"`，而不是一段随意填写的中文？

这一小步完成并验证后，再学习 `EvidenceStatus`。不要先写三个 Pydantic 模型。

### 第 2 步：学习一个最小的 Pydantic 模型

先用只有 `name: str` 的临时示例理解：字段、类型标注、创建实例和数据校验。理解后，再开始实现 `Profile`。

### 第 3 步：逐个增加默认值

依次学习并加入：

1. `target_roles` 的空列表默认值。
2. 使用 `uuid.uuid4` 生成 ID。
3. 使用 `datetime.now(timezone.utc)` 生成时间。
4. 为什么动态默认值要放进 `Field(default_factory=...)`。

### 第 4 步：迁移到另外两个模型

等 `Profile` 能创建后，再把已经理解的写法迁移到 `Capability` 和 `Evidence`。这一步是在重复练习，不是学习四个全新概念。

### 第 5 步：最后再学习 SQLite

三个模型通过验收脚本后，才开始数据库保存和读取。SQLite 不和前面的概念同时学习。

## 最终需要亲手完成的部分

打开 `src/job_agent/domain/models.py`，依次完成：

1. `CapabilityLevel`：`aware`、`assisted`、`independent`、`project_verified`。
2. `EvidenceStatus`：`candidate`、`confirmed`、`verified`、`rejected`。
3. `Profile`：用户身份、目标岗位和创建/更新时间。
4. `Capability`：属于哪个档案、能力名称、当前等级和更新时间。
5. `Evidence`：支持哪项能力、来源、摘要、验证状态和创建时间。

先不要添加岗位、分析结果或 LangGraph State。今天只处理这三个实体之间的关系：

```text
Profile 1 ---- n Capability 1 ---- n Evidence
```

## 字段约定

| 模型 | 字段 | 类型 |
|---|---|---|
| Profile | id | str，默认生成 UUID |
| Profile | name | str，不能为空 |
| Profile | target_roles | list[str]，默认空列表 |
| Profile | created_at | datetime，默认当前 UTC 时间 |
| Profile | updated_at | datetime，默认当前 UTC 时间 |
| Capability | id | str，默认生成 UUID |
| Capability | profile_id | str |
| Capability | name | str，不能为空 |
| Capability | level | CapabilityLevel，默认 aware |
| Capability | updated_at | datetime，默认当前 UTC 时间 |
| Evidence | id | str，默认生成 UUID |
| Evidence | capability_id | str |
| Evidence | source_type | str，例如 resume、conversation、code、run_result |
| Evidence | source_ref | str 或 None |
| Evidence | summary | str，不能为空 |
| Evidence | status | EvidenceStatus，默认 candidate |
| Evidence | created_at | datetime，默认当前 UTC 时间 |

提示：可使用 `uuid.uuid4`、`datetime.now(timezone.utc)` 和 Pydantic 的 `Field(default_factory=...)`。不要把 `uuid4()` 或 `datetime.now(...)` 直接写成类字段的固定默认值，否则所有实例可能共享定义类时生成的值。

## 验收顺序

1. 运行 `python scripts/day1_smoke.py`，观察当前失败信息。
2. 每完成一个枚举或模型就重新运行。
3. 验收脚本通过后，再实现 SQLite 保存和读取。
4. 最后确认从数据库读出的 ID、枚举值和文本与写入前一致。

不要一次复制完整答案。遇到第一处不懂或失败，把对应代码和完整报错交给我，我们只解决那一个概念。
