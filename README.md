# Career Evidence Agent

这是一个面向真实求职过程的证据驱动 Agent。它根据岗位要求检索个人能力证据；证据不足时继续追问；用户确认新证据后，系统更新能力档案并重新分析岗位。

## 第一阶段闭环

```text
输入 JD -> 提取要求 -> 检索证据 -> 分析匹配
                                  |
                         关键证据是否充分？
                          /              \
                        是                否
                        |                 |
                    保存报告          追问用户
                                          |
                                      候选证据
                                          |
                                      用户确认
                                          |
                                  更新档案并重新分析
```

## 当前进度

- [x] 确认产品范围和技术边界
- [x] 建立项目骨架
- [x] 完成 Day 1 核心数据模型
- [x] 实测 SQLite 保存并读取档案、能力和证据
- [x] 补齐 Day 1 非空校验与数据库自动验收
- [x] 完成 Day 2 完整档案读取和 Chroma 可追溯检索
- [x] 提交 Day 2 候选证据规则的强化断言
- [x] 完成 Day 3 JD 结构化抽取

学习记录见 [Day 1](docs/day-01.md)、[Day 2](docs/day-02.md) 和 [Day 3](docs/day-03.md)。架构边界见 [docs/architecture.md](docs/architecture.md)。
