---
name: iterative-code-review
description: >
  Use when 开发者要求在提交或合并前审查工作区、暂存区或分支 diff，尤其是明确要求
  review-and-fix、修复后复验或迭代到收敛时。适用于 Codex 和 Claude 的隔离 sub-agent 工作流；
  若用户要求可配置的外部 CLI 多模型与人工勾选流程，使用 multi-agent-review。
---

# Iterative Code Review

把主开发 session 当作薄控制面：它只推断模式、生成短需求摘要、调度隔离 agent，并转发最终压缩报告。
完整 diff、源码、详细 findings、修复过程和测试日志始终通过 Git 内部 artifact 交接，不进入主 session。

## 调用兼容性

原有的一句话调用继续有效，无需用户每次提供需求或参数：

```text
使用 iterative-code-review 做 review fix 迭代
review and fix my changes with iterative-code-review
```

模式自动推断：

- 明确出现 `fix`、`修复`、`review-and-fix` 或“修复后迭代” → `review-and-fix`。
- 只要求 `review`、检查或报告 → `review-only`，禁止修改工作区。
- 用户显式指定模式时，以用户输入为准。

## 参数

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `mode` | 自动推断 | `review-only` 或 `review-and-fix` |
| `max_iterations` | `3` | 包含初始 review；相同问题重复或无进展时提前停止 |
| `base` | 自动检测 | 显式值优先；否则尝试远端默认分支、本地 `main/master` |
| `verification_policy` | `trusted-full-access` | 默认继承可信开发 session 的宿主权限且无需逐条确认；不可信仓库显式选择 `no-exec` |

## 上下文隔离契约

主 session 只允许保留：

- 工作目录、`mode`、`base`、轮次和 artifact 路径；
- 从当前开发对话压缩出的 3～10 条 `task_contract`；
- agent 的完成回执和最终短报告。

主 session **不读取完整 diff**、源码、reviewer JSON、完整测试日志，也不亲自聚合 findings 或应用修复。
reviewer、synthesizer、fixer、verifier 通过文件传递详细信息，最终响应必须遵守生成 prompt 中的长度限制。

运行 artifact 写入 Git 内部路径：

```text
<git-path>/iterative-code-review/<run-id>/iteration-N/
```

它不会进入工作树或被提交。不要把 artifact 内容复制回主对话。

## 需求上下文自动提取

用户不需要额外提供需求。主 session 在不复制完整对话的前提下，按顺序生成短 `task_contract`：

1. 当前 session 中明确的原始需求和验收标准；
2. 用户给出的 spec、plan、issue、PR 或文档路径；
3. 若仍无可靠来源，留空。

不得从 diff 或现有实现反推需求。需求为空时，requirements reviewer 标记“无法验证”并继续其他维度；
只有需求歧义会改变公开行为或触发 High impact 修复时，才向用户询问。

将摘要写到工作树之外的临时文件时使用环境提供的文件编辑工具；不要把用户文本插值进 shell 命令。

## 工作流

### 1. 冻结本轮范围并生成 prompt

运行 skill 自带脚本；它只向主 session 输出短 JSON 路径索引，diff 内容直接落盘：

```bash
python <skill-dir>/scripts/prepare_review.py \
  --repo <WORKDIR> \
  --mode <review-only|review-and-fix> \
  [--base <ref>] \
  [--verification-policy <trusted-full-access|no-exec|sandboxed|approved>] \
  [--approved-command <exact-command>] \
  [--task-contract-file <temporary-contract-file>]
```

默认 `trusted-full-access`：sub-agent 继承宿主为当前可信开发 session 提供的 full access，无需逐条确认。
skill 不授予或提升宿主权限，也不会把 full access 伪装成沙箱。不熟悉或不信任仓库内容时，显式选择 `no-exec`。
只有宿主明确证明当前环境是隔离的真实沙箱时才选择 `sandboxed`。
`approved` 只接受用户逐条明确批准的完整命令字符串，且 `--approved-command` 可重复。

后续轮次复用返回的 `run_id`，增加 `--iteration N`。范围同时包含：

- `base...HEAD` 的已提交改动；
- staged；
- unstaged；
- untracked 文件清单与不超过 runner 限额的内容快照；超限文件记录 scope limitation。

在 `main/master` 上没有 base 时，只审查 working tree。脚本无法可靠推断 base 时继续 working-tree review，
并在报告中说明 committed branch diff 未验证；不要猜测不存在的远端引用。

### 2. 隔离并行 review

读取脚本返回的 `reviewer_prompts` 路径，只把“读取该 prompt 并执行”的最小消息发给 fresh-context agent：

- Codex：使用隔离 agent，能控制继承时设置 `fork_turns=none`。
- Claude：使用 fresh-context sub-agent，只传 prompt 文件路径，不传开发对话。
- 其他环境：使用等价 agent API；没有 sub-agent 时明确报告无法满足隔离契约，不在主 session 降级读取 diff。

采用**动态并发**：并发数不超过可用槽位减去主 session；槽位不足时分批或顺序执行。
三个角色覆盖：

1. 需求完整性、逻辑正确性、边界情况；
2. 安全性、可靠性、性能；
3. 代码质量、测试覆盖、实际运行命令识别。

每个 reviewer 把详细 JSON 写入 artifact，最终只返回一行完成回执。
全部完成后，不读取 JSON 内容，改用 runner 校验结构：

```bash
python <skill-dir>/scripts/prepare_review.py \
  --validate-artifact-dir <iteration-artifact-dir> \
  --validate-phase reviewers
```

随后用 `--validate-phase scope` 确认工作区仍与冻结范围一致。汇总、修复和验证前都必须再次校验 scope；
若指纹变化，本轮结果作废，回到阶段 1 生成新 iteration，禁止对旧 findings 应用修复。

校验失败时仅重试对应 agent 一次；仍失败则停止并报告 artifact 不完整，不能把缺失结果当作无问题。

### 3. 隔离汇总

启动 fresh-context synthesizer，只传 `synthesis_prompt` 路径。它负责：

- 按根因和证据去重；
- 区分 `severity`、`confidence`、`impact`，禁止平均 confidence 或用 impact 修改 confidence；
- 保留有证据的 Critical/High 和确实增加本次风险的 Medium，过滤纯 nit；
- 写入 `summary.json`，只返回不超过 10 行的 blocker 摘要。

finding 可以位于调用方、测试或配置中，但必须说明它如何由本次改动引入或直接暴露。
完成后用同一 runner 的 `--validate-phase synthesis` 校验，不在主 session 打开 `summary.json`。

### 4. 独立运行验证

启动 fresh-context verifier，只传 `verify_prompt` 路径。由它读取项目 manifest、CI 和文档，执行最强可行的：

- 相关测试；
- lint、typecheck、build；
- 完整测试或安全的本地 smoke test。

实际执行受 `verification_policy` 约束：

- `trusted-full-access`（默认）：可信仓库中继承宿主 full access 直接执行验证，无需逐条确认；仍禁止联网、凭证、危险命令及未经授权的外部写入。
- `no-exec`：只发现命令，全部按真实 `required` 值记为 skipped，不执行仓库或项目命令，结论不得为 green。
- `sandboxed`：仅在宿主证明的真实沙箱内执行，并继续禁止联网、凭证、危险命令及未经授权的写入。
- `approved`：只执行 allowlist 中完全一致的命令字符串，其他命令全部 skipped。

用户明确批准命令后，必须创建新的 iteration，不得改写旧 artifact；重复传入精确命令：

```bash
python <skill-dir>/scripts/prepare_review.py \
  --repo <WORKDIR> \
  --run-id <run-id> \
  --iteration <next-N> \
  --mode <review-only|review-and-fix> \
  --verification-policy approved \
  --approved-command '<exact-command-1>' \
  --approved-command '<exact-command-2>'
```

每条结果记录 command、exit code、状态和证据。禁止部署、破坏性命令、真实凭证调用和未经授权的外部写入。
命令可能写源码且无法放入安全临时副本时跳过并记录限制。
必需检查失败时不得标记 green；全部跳过时不得声称“可安全合并”。
完成后使用 `--validate-phase verification` 校验 artifact。

### 5. 可选修复

`review-only` 跳过本阶段。

`review-and-fix` 中，启动 fresh-context fixer，只传 `fix_prompt` 路径：

- 自动修复仅限 High confidence、Low/Medium impact 的 Critical/High finding；
- High impact 必须暂停并请求用户确认，impact 与 confidence 不做数学换算；短回执最多列出 3 个候选的 `ID | 行为影响 | 拟议修复`；
- 用户确认后，主 session 只把获批 ID 交给 runner 校验并写入授权文件，不读取或复制完整 summary：

```bash
python <skill-dir>/scripts/prepare_review.py \
  --approve-artifact-dir <iteration-artifact-dir> \
  --approve-id <finding-id> [--approve-id <finding-id>]
```

主 session 只保留 runner 返回的短 `approval_digest`。启动 fixer 前和完成后都执行：

```bash
python <skill-dir>/scripts/prepare_review.py \
  --approve-artifact-dir <iteration-artifact-dir> \
  --validate-approval-digest <approval-digest>
```

任一次不匹配都拒绝接受修复结果；fixer 无权修改授权文件。未发生 High-impact 确认时，使用阶段 1 返回的初始 digest。
digest 只证明 artifact 前后字节一致，不是针对同权限恶意 agent 的安全边界。当前 runner 不提供按 finding 的写能力隔离或条件 patch 应用，
因此 High-impact 项即使得到确认也不由本轮 fixer 执行：记录确认后停止，并把该 ID 交给用户另行发起显式实现任务。
- 能测试的缺陷先建立会因该缺陷失败的最小回归测试，再做最小修复；
- 不重构无关代码，不覆盖用户改动，不提交、不推送、不创建 PR。

修复后回到阶段 1，重新冻结 updated diff 并 review。主 session 不亲自编辑。
修复 agent 完成后使用 `--validate-phase fixes` 校验 artifact；校验失败不得进入下一轮。

### 6. 收敛与最终报告

满足以下全部条件才算收敛：

```text
无未解决 blocker
AND 必需验证为 green
AND 本轮没有产生新的 actionable finding
```

需求“无法验证”不是自动失败，但最终结论必须带限制。出现以下任一条件提前停止并报告：

- 达到 `max_iterations`；
- 相同 finding 在连续两轮重复；
- 工作树没有变化且验证仍失败；
- 需要用户确认的 High impact 修复。

最后启动 fresh-context reporter，只传 `report_prompt` 路径。完整报告写入 artifact，主 session 只转发其短报告，包含：

- 需求验证状态；
- 已修复与未解决数量；
- 实际运行的验证及结果；
- 遗留风险、跳过项和带条件的合并建议；
- 完整 artifact 路径。

## 约束

- 只处理由本次改动引入或直接暴露的问题；允许读取必要上下文，但不顺手清理旧问题。
- 不因风格、个人偏好或推测性优化修改代码。
- 不新增无关依赖、抽象、重命名或类型注解。
- 不添加 AI 署名，不 commit、push、建 PR，除非用户另行明确要求。
- 不把 agent 详细输出、diff 或日志重新注入主开发 session。
