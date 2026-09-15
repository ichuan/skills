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
安全后果按调用者实际权限和被突破的边界判断；缺少最佳实践、已授权操作或单独出现 prompt injection 文本都不足以认定漏洞。

## Confidence：证据强度

| 等级 | 标准 |
|---|---|
| High | 已由失败测试/命令复现，或存在完整且无关键假设的代码路径证据 |
| Medium | 因果链可信，但依赖一个尚未验证的环境、输入规模或调用方假设 |
| Low | 主要是猜测、缺少触发条件，或需要未知上下文才能成立 |

自动修复只考虑 High confidence。没有 `trigger_or_scenario`、`change_causality` 和 `evidence` 的 finding 直接丢弃。

## 安全 finding 的独立复核

安全 finding 使用 `category=security:<class>`（也识别 `security`），并带完整 `security_context`：
`entrypoint`、`principal`、`boundary`、`asset`、`control`、`impact` 均为非空字符串。
`security_context.impact` 描述未授权结果；顶层 `impact` 仍描述修复范围。

独立 verifier 尝试推翻汇总中保留的每个安全 finding，并在 `verification.json.security_checks` 写入
`finding_id`、`status`、`method`（`source|local`）、`evidence` 和 `test_or_gap`：

| status | 证据与处理 |
|---|---|
| `confirmed` | 入口、实际权限、控制缺口与未授权后果的因果链成立；仍须满足原有 severity/confidence/impact 条件才能自动修复 |
| `needs_validation` | 环境、权限、可达性或结果仍有关键假设；说明缺失证据和验证方法，不得自动修复或给出无条件合并建议 |
| `rejected` | 已有控制、权限事实或不可达路径推翻该 finding；保留复核依据，从有效 blocker 和自动修复中排除 |

`method=source` 可凭完整源码证据确认，无需强制动态 PoC。`method=local` 必须有真实执行的命令、日志和
`commands[].finding_ids` 关联；未执行的验证记录缺口，跳过命令可用 `skipped[].finding_ids` 关联。
复核状态不替代 `confidence`，也不改变现有 `verification_policy` 或其他 finding 的处理规则。

## Impact：修复爆炸半径

| 等级 | 标准 |
|---|---|
| Low | 函数内部或局部测试，不改公开合约 |
| Medium | 同一模块多处联动，但不改变公开接口、数据格式或迁移 |
| High | 公开 API、数据模型、迁移、跨模块行为、部署或用户可见语义发生改变 |

High impact 不代表 finding 不可信；它代表自动修复权限不足。有效的 High impact finding 直接作为 blocker 留在本轮结果中。

## 处理规则

- 报告：有证据的 Critical/High，以及确实增加本次改动风险的 Medium。
- 自动修复：仅 `Severity ∈ {Critical, High}`、`Confidence = High`、`Impact ∈ {Low, Medium}`；安全 finding 还须独立复核为 `confirmed`。
- High impact：直接保持 blocker；本轮不请求确认，也不交给 fixer。报告建议另起显式实现任务。
- Medium：默认只报告，不在自动迭代中顺手重构。
- verifier 与 fixer 共享同一 `verification_policy`。允许正常可再生的 build/cache 输出，禁止源码或用户文件变化；runner 校验 artifact 不等于证明真实 sub-agent 执行。
- 合并建议：一轮无未解决 blocker 且必需验证 green 即可给出；不要求跑满两轮。需求无法验证或检查跳过时必须限定结论。
