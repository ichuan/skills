---
name: multi-agent-review
description: Run a configurable multi-model code review workflow from local CLI agents. Use when a developer wants AI review for uncommitted diffs or a branch diff before commit/merge, with separate review, synthesis, human selection, fix, and verify phases using Claude Code or Codex CLI.
---

# Multi Agent Review

Use `scripts/review_forge_runner.py` to run a local Review Forge style workflow:

1. Multiple configured models independently review the selected diff.
2. One configured model synthesizes the review reports into `summary.md`.
3. The user edits `summary.md` and checks the issues worth fixing.
4. A configured fix model modifies the current worktree and runs tests.
5. A configured verify model independently checks the fix.

The main session should orchestrate and report results. Do not paste full diffs or large review logs into the main conversation unless the user asks.

## Setup

Initialize local configuration from the target repository root:

```bash
python <skill-dir>/scripts/review_forge_runner.py init
```

This creates:

- `.review-forge/config.local.yaml`
- `.review-forge/`
- a local ignore entry in `.git/info/exclude` for `.review-forge/`

The local config may contain API keys. Keep it out of git. Prefer environment placeholders such as `${DEEPSEEK_API_KEY}` when practical.

After `init`, stop and ask the user to review `.review-forge/config.local.yaml`. The runner will refuse review, synthesize, fix, and verify until `config_ready: true` is set. Do not set it for the user unless they explicitly approve the model configuration.
Offer to run `check-config` after the user edits the config. It sends a short harmless prompt to each configured role model without enabling dangerous permissions, so CLI/model/token problems surface before the review workflow starts.

See `references/config.md` for the supported config shape.

## Scope

Before running review, determine the target diff scope.

- If the user explicitly asks for uncommitted changes, use `--scope working`.
- If the user explicitly asks for changes against a branch, use `--base origin/main`, `--base origin/master`, or the requested ref.
- If the user does not specify, ask one concise question before running review.

When `--base` is used, the runner includes both `git diff <base>...HEAD` and the current working tree diff.
For both scope modes, the runner also includes small untracked text files, while excluding `.review-forge/`.

## Commands

Run from the repository root.

```bash
# Create local config
python <skill-dir>/scripts/review_forge_runner.py init

# After reviewing model settings, edit .review-forge/config.local.yaml:
# config_ready: true

# Optional: smoke test configured review/synthesize/fix/verify models before enabling workflow
python <skill-dir>/scripts/review_forge_runner.py check-config

# Review uncommitted changes
python <skill-dir>/scripts/review_forge_runner.py review --feature checkout-refactor --scope working

# Review current branch against origin/main, including uncommitted changes
python <skill-dir>/scripts/review_forge_runner.py review --feature checkout-refactor --base origin/main

# Summarize independent reports
python <skill-dir>/scripts/review_forge_runner.py synthesize --feature checkout-refactor

# After the user checks items in summary.md
python <skill-dir>/scripts/review_forge_runner.py fix --feature checkout-refactor

# Verify the fix with a different model
python <skill-dir>/scripts/review_forge_runner.py verify --feature checkout-refactor
```

Artifacts are written under:

```text
.review-forge/artifacts/<feature>/
  reviews/
  logs/
  summary.md
  fix-plan.md
  status.md
  verify.md
  pre-fix.diff
```

## Workflow Rules

- Review agents must be treated as read-only. The runner captures stdout and writes reports itself.
- The runner writes large task prompts to `.review-forge/runs/` to avoid command-line length limits.
- `check-config` may run before `config_ready: true`; it must not enable dangerous permissions.
- Synthesize must read existing reports and produce only `summary.md`.
- Stop after synthesis. The user must choose issues by editing checkboxes in `summary.md`.
- Fix may directly modify the current worktree. Before fixing, preserve `pre-fix.diff`.
- Verify must be independent from fix. Prefer a different configured model.
- Keep changes surgical. Fix only checked issues.
- Do not commit, push, or open a PR unless the user asks.

## Model Roles

Use config keys:

- `review_models`: first three entries are used for review.
- `synthesize_model`: used for summary; if omitted, fallback to the first review model.
- `fix_model`: used for implementation.
- `verify_model`: used for independent verification.

First version supports `claude` and `codex` adapters only.

## Reporting Back

After each runner command, summarize:

- command outcome
- files written
- failed model runs, if any
- next required user action

Do not dump raw logs unless needed for debugging.
