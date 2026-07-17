# Finding Severity, Confidence & Impact

三个字段相互独立。不要平均不同 reviewer 的 confidence，也不要因为影响范围大而数值化降低 confidence。

## Severity：问题后果

| 等级 | 标准 |
|---|---|
| Critical | 可利用的严重安全漏洞、数据丢失/损坏、关键生产中断或不可逆合约破坏 |
| High | 现实路径上的错误结果、权限绕过、显著可靠性/性能退化、必需测试或构建失败 |
| Medium | 有证据的边缘缺陷、测试缺口、兼容性或维护性风险，但不阻断主要路径 |
| Low | 非阻断建议；纯风格和个人偏好通常不应上报 |

Severity 必须同时考虑影响、可达性、发生可能性和受影响范围。安全、重试、事务、N+1 等关键词本身不自动决定级别。

## Confidence：证据强度

| 等级 | 标准 |
|---|---|
| High | 已由失败测试/命令复现，或存在完整且无关键假设的代码路径证据 |
| Medium | 因果链可信，但依赖一个尚未验证的环境、输入规模或调用方假设 |
| Low | 主要是猜测、缺少触发条件，或需要未知上下文才能成立 |

自动修复只考虑 High confidence。没有 `trigger_or_scenario`、`change_causality` 和 `evidence` 的 finding 直接丢弃。

## Impact：修复爆炸半径

| 等级 | 标准 |
|---|---|
| Low | 函数内部或局部测试，不改公开合约 |
| Medium | 同一模块多处联动，但不改变公开接口、数据格式或迁移 |
| High | 公开 API、数据模型、迁移、跨模块行为、部署或用户可见语义发生改变 |

High impact 不代表 finding 不可信；它代表自动修复权限不足，必须请求用户确认。

## 处理规则

- 报告：有证据的 Critical/High，以及确实增加本次改动风险的 Medium。
- 自动修复：仅 `Severity ∈ {Critical, High}`、`Confidence = High`、`Impact ∈ {Low, Medium}`。
- High impact：保持 blocker，等待用户确认。
- Medium：默认只报告，不在自动迭代中顺手重构。
- 合并建议：只有无 blocker 且必需验证 green 时才可给出；需求无法验证或检查跳过时必须限定结论。
