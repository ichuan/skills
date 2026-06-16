# Multi Agent Review Config

Config path:

```text
.review-forge/config.local.yaml
```

This file is local-only and may contain secrets. The runner adds it to `.git/info/exclude` when running inside a git repository.
The runner also ignores `.review-forge/runs/`, where full prompts with diffs are stored for CLI invocations.
Review artifacts are stored under `.review-forge/artifacts/`.
Run `check-config` after editing this file if the user wants to test CLI/model/token connectivity before enabling the workflow.

## Example

```yaml
# 配置确认开关：确认下面的 CLI、模型名、环境变量和测试命令都可用后，才改成 true。
config_ready: true

# Review 阶段使用的模型 ID 列表：runner 会取前三个模型并行独立审查 diff。
review_models:
  - deepseek-via-claude
  - gpt-via-codex
  - sonnet-via-claude

# 汇总阶段使用的模型 ID：负责把多份 review 报告合并成 summary.md。
synthesize_model: gpt-via-codex

# 修复阶段使用的模型 ID：会直接修改当前工作区，建议配置成能力最强、最稳定的模型。
fix_model: sonnet-via-claude

# 验证阶段使用的模型 ID：应不同于 fix_model，用来独立检查修复是否完成。
verify_model: gpt-via-codex

# 单个 CLI agent 最长运行时间，单位秒。
timeout_seconds: 1800

# 修复和验证阶段要运行的测试命令；不知道时可留空，由 agent 自行选择最小相关测试。
test_command: npm test

# 模型定义表：上面的 review_models / synthesize_model / fix_model / verify_model 都必须引用这里的某个 ID。
models:
  # 通过 Claude Code CLI 调 DeepSeek Anthropic-compatible API 的示例。
  deepseek-via-claude:
    # cli：调用哪个本地命令，目前支持 claude 和 codex。
    cli: claude
    # model：传给对应 CLI 的模型名；可用值取决于你本机 CLI 和账号/provider 配置。
    model: deepseek-v4-pro
    # env：只对这个模型调用生效的环境变量；建议用 ${ENV_VAR} 引用系统环境变量。
    env:
      ANTHROPIC_BASE_URL: https://api.deepseek.com/anthropic
      ANTHROPIC_AUTH_TOKEN: ${DEEPSEEK_API_KEY}
      ANTHROPIC_MODEL: deepseek-v4-pro

  # 通过 Claude Code 自身认证使用 sonnet 的示例。
  sonnet-via-claude:
    cli: claude
    model: sonnet

  # 通过 Codex CLI 使用 Codex 可用模型的示例。
  gpt-via-codex:
    cli: codex
    model: gpt-5.5
```

## Fields

- `config_ready`: must be `true` before any workflow command runs. Leave it `false` until the user has reviewed CLI/model/env settings.
- `review_models`: ordered model IDs. The runner uses the first three.
- `synthesize_model`: model ID for report synthesis. Defaults to `review_models[0]`.
- `fix_model`: model ID for code changes.
- `verify_model`: model ID for independent verification.
- `timeout_seconds`: optional per-agent timeout. Defaults to `1800`.
- `test_command`: optional test command passed to fix and verify prompts.
- `models`: map of model ID to adapter settings.

## Model Settings

- `cli`: `claude` or `codex`.
- `model`: model name passed to the CLI.
- `env`: extra environment variables for only this invocation.
- `args`: extra CLI arguments appended to the invocation.
- `dangerous`: optional boolean. If true, use the adapter's broad permission bypass.

Use `${VAR_NAME}` to read a value from the current process environment.

## Connectivity Check

`check-config` does not require `config_ready: true`. It sends a short prompt to each unique configured role model from `review_models`, `synthesize_model`, `fix_model`, and `verify_model`, writes logs under `.review-forge/artifacts/config-check/logs/`, and reports failures before the real workflow starts.

```bash
python <skill-dir>/scripts/review_forge_runner.py check-config
```
