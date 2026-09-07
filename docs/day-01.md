# Day 1：核心数据模型与 SQLite

目标：能够创建一份个人档案，为它添加能力和证据，并从 SQLite 读回相同内容。

## 你需要亲手完成的部分

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

