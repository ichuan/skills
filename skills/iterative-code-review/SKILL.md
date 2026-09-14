---
name: iterative-code-review
description: >
  Use when 开发者要求在提交或合并前审查工作区、暂存区或分支 diff，尤其是明确要求
  review-and-fix、修复后复验或迭代到收敛时。适用于 Codex、Claude 以及具备独立会话能力的其他宿主；
  若用户要求可配置的外部 CLI 多模型与人工勾选流程，使用 multi-agent-review。
---

# Iterative Code Review

主场景是独立功能完成后的 `review-and-fix`。把主开发 session 当作薄控制面：它只推断模式、生成短需求摘要、调度隔离 agent，并转发最终压缩报告。
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
| `max_iterations` | `8` | 仅为上限，包含初始 review；轮次只能递增，不能覆盖既有 iteration；相同问题重复或无进展时提前停止 |
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
只有需求歧义会改变公开行为时，才向用户询问。

将摘要写到工作树之外的临时文件时使用环境提供的文件编辑工具；不要把用户文本插值进 shell 命令。

## 工作流

### 角色与交接

主 agent 只按宿主实际能力调度角色和阶段，不把某个模型名称当作隔离能力。每个角色只接收上游 artifact 路径并写回约定输出：

| 角色 | 输入 | 输出与职责 |
|---|---|---|
| 需求/风险/质量 reviewers（三个平级角色） | 冻结范围、对应 reviewer prompt、短 `task_contract` | 各自的 JSON finding；分别覆盖需求与正确性、风险与性能、质量与测试/命令证据。三者可并行。 |
| 汇总 synthesizer | 三份 reviewer JSON、scope artifact | `summary.json`：按根因去重，标注 severity/confidence/impact 和修复候选。 |
| 验证 verifier | scope、`summary.json`、`verify_prompt`、`verification_policy` | `verification.json`：实际命令、exit code、状态、证据和跳过原因；不改源码或用户文件。 |
| 修复 fixer（仅 review-and-fix） | scope、允许的修复候选、`fix_prompt`、同一 `verification_policy` | `fixes.json` 和最小代码修复；只处理允许的候选，不改授权文件。 |
| 报告 reporter | 全部阶段 artifact 路径、最终 gate 状态 | 面向用户的短报告和完整报告 artifact。 |

汇总、验证、修复、报告按依赖顺序由主 agent 调度；不要求某一宿主提供固定命令。任何角色无法获得独立上下文或必要文件能力时，必须如实报告并停止该阶段。

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

后续轮次复用返回的 `run_id`，只使用更大的 `--iteration N`，不得覆盖既有 iteration。范围同时包含：

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
- 其他宿主：使用等价的独立 agent/session API；没有 fresh session、文件或命令能力时明确报告无法满足隔离契约并停止，不在主 session 降级读取 diff。

宿主差异可能随版本漂移，先探测实际可用工具和能力；不要把模型名称等同于宿主隔离。

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

verifier 与 fixer 共享同一 `verification_policy`；实际执行受它约束：

- `trusted-full-access`（默认）：可信仓库中继承宿主 full access 直接执行验证，无需逐条确认；仍禁止联网、凭证、危险命令及未经授权的外部写入。允许正常可再生的 build/cache 输出，但禁止源码和用户文件变化。
- `no-exec`：只发现命令，全部按真实 `required` 值记为 skipped，不执行仓库或项目命令，结论不得为 green。
- `sandboxed`：仅在宿主证明的真实沙箱内执行，并继续禁止联网、凭证、危险命令及未经授权的写入；允许正常可再生的 build/cache 输出，但禁止源码和用户文件变化。
- `approved`：只执行 allowlist 中完全一致的命令字符串，其他命令全部 skipped；允许正常可再生的 build/cache 输出，但禁止源码和用户文件变化。

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

每条结果记录 command、exit code、状态和证据。禁止部署、破坏性命令、真实凭证调用和未经授权的外部写入。runner 只校验 artifact 结构和范围，不证明真实 sub-agent 已执行。
命令可能写源码且无法放入安全临时副本时跳过并记录限制。
必需检查失败时不得标记 green；全部跳过时不得声称“可安全合并”。
完成后使用 `--validate-phase verification` 校验 artifact。

### 5. 可选修复

`review-only` 跳过本阶段。

`review-and-fix` 中，启动 fresh-context fixer，只传 `fix_prompt` 路径：

- 自动修复仅限 `Severity ∈ {Critical, High}`、`Confidence = High`、`Impact ∈ {Low, Medium}` 的 finding；
- High impact 直接作为 blocker 保留，不在本轮请求无作用的确认；报告建议另起显式实现任务。impact 与 confidence 不做数学换算；



fixer 无权修改授权文件；runner 的 digest 只证明 artifact 前后字节一致，不是针对同权限恶意 agent 的安全边界。High-impact 项不交给本轮 fixer 执行。
- 能测试的缺陷先建立会因该缺陷失败的最小回归测试，再做最小修复；
- 不重构无关代码，不覆盖用户改动，不提交、不推送、不创建 PR。

修复后回到阶段 1，重新冻结 updated diff 并 review。主 session 不亲自编辑。
修复 agent 完成后使用 `--validate-phase fixes` 校验 artifact；校验失败不得进入下一轮。

当前 iteration 的 reviewers、synthesizer、verifier（以及存在的 fixer artifact）全部完成后，确认不再继续修复、启动 reporter 前运行最终 gate：

```bash
python <skill-dir>/scripts/prepare_review.py \
  --validate-artifact-dir <iteration-artifact-dir> \
  --validate-phase final
```

主 session 只根据返回的 `status`、`counts`、`limitations`、`merge_ready` 和 `stop_reason` 推进或报告；`continue` 才能进入 fixer/下一轮，`converged` 才能在没有限制时建议合并，`review_complete` 只表示 review-only 已完成，`blocked` 必须保留阻塞原因。

### 6. 收敛与最终报告

一轮完成且满足以下条件即可收敛，不要求跑满两轮：

```text
无未解决 blocker
AND 必需验证为 green
```

需求“无法验证”不是自动失败，但最终结论必须带限制。出现以下任一条件提前停止并报告：

- 达到 `max_iterations`；
- 相同 finding 在连续迭代中重复；
- 工作树没有变化且验证仍失败；
- High impact blocker 需要另起显式实现任务。

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
