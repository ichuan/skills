---
name: iterative-code-review
description: >
  对本次 diff 进行多维 code review 并自动修复，循环迭代直到收敛或达到最大轮次。
  适用场景：开发完成一个 feature 或 fix 后，在提交/建 MR 前做质量保障。
  触发关键词：「code review」「review 一下代码」「使用 iterative-code-review skill」
  「review and fix」「做 code review」「检查代码质量」。
---

# Iterative Code Review & Auto-Fix

对本次改动（diff against main/target branch）执行多 agent 并发 review，
主 session 聚合结果、过滤噪音、修复真实问题，并循环迭代直至收敛。

## 设计原则

1. **Diff 隔离**：仅分析本次改动引入的新增/修改行，预先存在的问题不在此次范畴。
2. **最小干预**：只修 Critical / High 级别的真实 bug；风格、命名、锦上添花一律跳过。
3. **置信度门槛**：Confidence < 0.70 的 issue 默认跳过，防止误改。
4. **Blast Radius 控制**：影响公开接口或跨模块的修复，需二次确认 / 降低置信度后才执行。
5. **迭代收敛**：修复后自动重新 review，直到无剩余问题或达到 `max_iterations`。

---

## 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_iterations` | `8` | 最大迭代轮次 |
| `target_branch` | 自动检测 | 优先使用 `main`，不存在则回退到 `master` |
| `confidence_threshold` | `0.70` | 低于此值的 issue 不处理 |
| `fix_impact_limit` | `MEDIUM` | 超出此 impact 等级则跳过（可选 LOW / MEDIUM / HIGH） |

---

## 调用方式

```
完成 <feature/fix> 的代码和测试后，使用 iterative-code-review skill 做 code review。

参数：
- max_iterations = 5
```

---

## 完整工作流

### 阶段 0：准备上下文（主 session 只做一次）

主 session **不**在自己的上下文中执行 git 命令或载入 diff 内容。
主 session 只需确定以下两件事，传递给后续每个 sub-agent：

1. **target_branch 检测指令**（sub-agent 自行执行）：

```bash
# sub-agent 应在工作目录中执行以下命令来确定基准分支：
git branch -r | grep -q 'origin/main' && echo main || echo master
# 将输出结果作为 <target_branch> 使用
```

2. **diff 获取指令**（sub-agent 自行执行，不传 diff 内容给主 session）：

```bash
# 确定 target_branch 后，sub-agent 运行：
git --no-pager diff origin/<target_branch>...HEAD
git --no-pager diff --name-only origin/<target_branch>...HEAD
```

> 主 session 上下文中只保留：「当前工作目录路径」和「传递给 sub-agent 的上述两条指令」。
> diff 原文、文件列表均由各 sub-agent 自己获取，不注入主 session。

---

### 阶段 1：多 Agent 并发 Review（每轮执行一次）

使用 `runSubagent` **并行**启动 5 个独立 reviewer，互不干扰。

> **重要**：每个 sub-agent 自行在项目目录中运行 git 命令获取 diff，**主 session 不传入 diff 内容**。
> 主 session 只在 prompt 中告知 sub-agent：工作目录路径、branch 检测方法、输出格式要求。

各 reviewer 的 prompt 模板如下（`<WORKDIR>` 替换为实际项目路径）：

#### Reviewer A — Correctness（逻辑正确性）

```
Prompt:
你是一个代码逻辑审查员。

首先在工作目录 <WORKDIR> 执行以下命令获取本次改动：
  1. 检测基准分支：git branch -r | grep -q 'origin/main' && echo main || echo master
  2. 获取 diff：git --no-pager diff origin/<target_branch>...HEAD
  3. 获取改动文件列表：git --no-pager diff --name-only origin/<target_branch>...HEAD

仅分析上述 diff 中新增/修改的行，不分析 diff 范围之外的代码。

重点检查：
- 逻辑错误 / 边界条件
- Null / None / undefined 处理
- 并发竞态条件 / 线程安全
- 循环 / 递归终止条件
- 数据类型不匹配
- 遗漏的边界 case（off-by-one、空集合、负数）
- debug 输出（console.log / print / pprint）遗留在代码中

详细检查项参见 references/review-checklist.md 中的 "Correctness & Reliability" 部分。

严格输出格式（每个 issue 一条，不得省略字段）：

Severity: Critical|High|Medium|Low
Category: Bug
Location: <文件名>:<行号>
Issue: <一句话描述>
Why it matters: <为什么这会出问题>
Fix: <最小化修复方案>
In-scope: Yes|No  (No = 此行在本次 diff 之外)
Confidence: 0.0–1.0

若无任何 issue，输出：NO_ISSUES
```

#### Reviewer B — Security（安全性）

```
Prompt:
你是一个安全代码审查员。

首先在工作目录 <WORKDIR> 执行以下命令获取本次改动：
  1. 检测基准分支：git branch -r | grep -q 'origin/main' && echo main || echo master
  2. 获取 diff：git --no-pager diff origin/<target_branch>...HEAD
  3. 获取改动文件列表：git --no-pager diff --name-only origin/<target_branch>...HEAD

仅分析上述 diff，重点检查（OWASP Top 10）：
- 注入攻击（SQL / Command / LDAP Injection）
- 不安全的反序列化
- 敏感数据 / Secret 硬编码或泄漏（API keys、密码、token）
- 身份认证 / 权限校验缺失
- 路径穿越（Path Traversal）
- XSS / CSRF 风险
- 用户输入未经验证直接使用
- CORS 配置不当
- 明文传输敏感数据（密码、PII 未加密存储）

详细检查项参见 references/review-checklist.md 中的 "Security" 部分。

输出格式同上，Category 固定为 Security。若无任何 issue，输出：NO_ISSUES
```

#### Reviewer C — Performance（性能）

```
Prompt:
你是一个性能代码审查员。

首先在工作目录 <WORKDIR> 执行以下命令获取本次改动：
  1. 检测基准分支：git branch -r | grep -q 'origin/main' && echo main || echo master
  2. 获取 diff：git --no-pager diff origin/<target_branch>...HEAD
  3. 获取改动文件列表：git --no-pager diff --name-only origin/<target_branch>...HEAD

仅分析上述 diff，重点检查：
- N+1 查询
- 低效循环 / 重复计算（可提取到循环外的不变量）
- 不必要的内存分配（大对象、未释放的资源）
- 算法复杂度退化（O(n²) 或更差，当 O(n log n) 可行时）
- 数据库查询缺少索引（大表全表扫描）
- 大数据集未分页或流式处理
- 不必要的同步阻塞操作
- 重复加载本可缓存的资源

详细检查项参见 references/review-checklist.md 中的 "Performance" 部分。

输出格式同上，Category 固定为 Performance。若无任何 issue，输出：NO_ISSUES
```

#### Reviewer D — Reliability（可靠性）

```
Prompt:
你是一个可靠性代码审查员。

首先在工作目录 <WORKDIR> 执行以下命令获取本次改动：
  1. 检测基准分支：git branch -r | grep -q 'origin/main' && echo main || echo master
  2. 获取 diff：git --no-pager diff origin/<target_branch>...HEAD
  3. 获取改动文件列表：git --no-pager diff --name-only origin/<target_branch>...HEAD

仅分析上述 diff，重点检查：
- 异常 / 错误未捕获或被吞掉（catch 后无处理）
- 资源泄漏（文件句柄、数据库连接、锁未释放）
- 重试 / 超时缺失（外部调用）
- 关键操作缺少日志（无法追溯问题）
- 数据库操作缺少事务，错误时未回滚
- 使用 catch-all handler 掩盖真实错误
- finally / defer 块中的清理逻辑缺失
- HTTP 状态码不正确（成功操作返回 200 但实际失败）

详细检查项参见 references/review-checklist.md 中的 "Error Handling & Reliability" 部分。

输出格式同上，Category 固定为 Reliability。若无任何 issue，输出：NO_ISSUES
```

#### Reviewer E — Code Quality（代码质量）

```
Prompt:
你是一个代码质量审查员，专注于可维护性与最佳实践。

首先在工作目录 <WORKDIR> 执行以下命令获取本次改动：
  1. 检测基准分支：git branch -r | grep -q 'origin/main' && echo main || echo master
  2. 获取 diff：git --no-pager diff origin/<target_branch>...HEAD
  3. 获取改动文件列表：git --no-pager diff --name-only origin/<target_branch>...HEAD

仅分析上述 diff，重点检查：
- 函数 / 方法违反单一职责（过长、承担多个职责）
- 重复代码（DRY 原则）
- 魔法数字 / 魔法字符串未提取为命名常量
- 变量 / 函数命名含糊（data、tmp、flag、result 等）
- 注释掉的代码块遗留在提交中
- 复杂逻辑缺少必要的 Why 注释（不是 What 注释）
- 使用了已废弃的 API 或有已知漏洞的依赖版本
- 配置项硬编码（应外部化到环境变量或配置文件）
- 公开 API 文档未更新（函数签名变化但文档没跟上）
- REST 接口不符合约定（动词/状态码/路径风格不一致）

**注意**：仅上报 High / Critical 级别的质量问题（会导致明显维护负担或隐性 bug 的），
纯风格问题（缩进、括号风格等）一律不上报。

详细检查项参见 references/review-checklist.md 中的 "Code Quality & Best Practices" 部分。

输出格式同上，Category 固定为 CodeQuality。若无任何 issue，输出：NO_ISSUES
```

---

### 阶段 2：聚合与去重

收集 5 个 reviewer 的结果，主 session 执行：

1. **合并同源 issue**：相同文件 + 相近行 + 相同根因 → 合并为一条，Severity 取最高，Confidence 取均值。
2. **过滤条件**（同时满足所有条件才保留）：
   - `Severity ∈ {Critical, High}`
   - `In-scope == Yes`（文件在本次 diff 范围内）
   - `Confidence >= confidence_threshold`（默认 0.70）
3. 丢弃所有 Medium / Low issue（列入"已知但不修"清单，附在最终报告末尾）。

---

### 阶段 3：Blast Radius 评估（修复前）

对每个待修 issue，主 session 估算：

| 影响等级 | 判断标准 |
|----------|---------|
| `LOW` | 仅修改函数内部，不改签名、不影响调用方 |
| `MEDIUM` | 影响同一模块内的多个函数，但不改公开接口 |
| `HIGH` | 改变公开 API / 接口签名 / 跨模块影响 |

规则：
- `HIGH` impact → Confidence 降低 0.15，若降后低于 threshold → 跳过并在报告中标注 "Blocked: High Impact"。
- 禁止在此过程中引入新的抽象层或重构未改动的代码。

---

### 阶段 4：应用修复

对每个通过过滤的 issue：

1. 应用**最小化修复**，不重构非相关代码，不改变原有意图。
2. 修复后对该文件执行自我审查：
   - 是否引入新的 bug？
   - 是否过度工程化？
   - 是否改变了原有行为？
3. 若自我审查发现问题，撤销该修复并标记为 "Fix Reverted: Self-review failed"。

---

### 阶段 5：迭代判断

```
if (iteration >= max_iterations):
    → 终止，输出最终报告
elif (本轮无任何修复):
    → 收敛，终止，输出最终报告
else:
    → iteration++
    → 返回阶段 1（sub-agent 在下一轮自行重新运行 git diff 获取 updated diff）
```

---

## 最终报告格式

```markdown
## Code Review 最终报告

### 迭代统计
- 总迭代轮次: N / max_iterations
- 已修复 issue 数: X
- 跳过 issue 数: Y（含原因）
- 终止原因: 收敛 | 达到最大轮次

### 已修复问题
| # | 文件:行 | Severity | Category | 描述 | 置信度 |
|---|---------|----------|----------|------|--------|
| 1 | ...     | Critical | Bug      | ...  | 0.92   |

### 未修复 / 跳过问题（附原因）
| # | 文件:行 | Severity | 原因 |
|---|---------|----------|------|
| 1 | ...     | Medium   | 低于 severity 阈值 |
| 2 | ...     | High     | Blocked: High Impact |

### 遗留风险
（仅列真实的、未解决的风险，无则写"无"）

### 合并建议
- 🟢 可安全合并 / 🔴 存在未解决问题
- 原因: ...
```

---

## 重要约束（禁止事项）

- **禁止**修改本次 diff 范围之外的文件（除非该文件被我们的改动直接破坏）
- **禁止**以"代码风格"/"命名规范"/"更优雅"为由修改代码
- **禁止**添加未被要求的 refactor、重命名、类型注解
- **禁止**修改现有变量名（即使命名不好，不在此次范畴）
- **禁止**为了修复 issue 而引入新的第三方依赖
- **禁止** AI 署名（不添加 Co-authored-by 等署名到 commit）

## 参考资料

- `references/review-checklist.md` — 各维度详细检查项，reviewer prompt 中引用
- `references/severity-guide.md` — Severity 分级标准、决策树与 Confidence 评估指南
