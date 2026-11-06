> 📖 English | [中文](./README_ZH.md)

# Personal Skills Collection

A collection of reusable skill sets for AI coding agents like Claude Code, Cursor, and Windsurf.

## Overview

This repository contains Agent Skills that extend AI coding assistants with specialized capabilities. All skills follow the standard Agent Skills specification and can be installed using `npx skills add`.

## Installation

### Install from GitHub

```bash
# Install all skills
npx skills add ichuan/skills

# Install a specific skill
npx skills add ichuan/skills --skill roadmap-management
npx skills add ichuan/skills --skill iterative-code-review
npx skills add ichuan/skills --skill deploy-caddy-reverse-proxy
npx skills add ichuan/skills --skill repo-deploy-capture
npx skills add ichuan/skills --skill prod-readiness-audit
npx skills add ichuan/skills --skill multi-agent-review
npx skills add ichuan/skills --skill web-search-fetch

# Install globally (available in all projects)
npx skills add ichuan/skills --skill roadmap-management --global
npx skills add ichuan/skills --skill iterative-code-review --global
npx skills add ichuan/skills --skill deploy-caddy-reverse-proxy --global
npx skills add ichuan/skills --skill repo-deploy-capture --global
npx skills add ichuan/skills --skill prod-readiness-audit --global
npx skills add ichuan/skills --skill multi-agent-review --global
npx skills add ichuan/skills --skill web-search-fetch --global
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/ichuan/skills.git

# Copy to global skills directory
cp -r skills/skills/roadmap-management ~/.claude/skills/
cp -r skills/skills/iterative-code-review ~/.claude/skills/
cp -r skills/skills/deploy-caddy-reverse-proxy ~/.claude/skills/
cp -r skills/skills/repo-deploy-capture ~/.claude/skills/
cp -r skills/skills/prod-readiness-audit ~/.claude/skills/
cp -r skills/skills/multi-agent-review ~/.claude/skills/
cp -r skills/skills/web-search-fetch ~/.claude/skills/

# Or copy to project-local directory
mkdir -p ./.claude/skills
cp -r skills/skills/roadmap-management ./.claude/skills/
cp -r skills/skills/iterative-code-review ./.claude/skills/
cp -r skills/skills/deploy-caddy-reverse-proxy ./.claude/skills/
cp -r skills/skills/repo-deploy-capture ./.claude/skills/
cp -r skills/skills/prod-readiness-audit ./.claude/skills/
cp -r skills/skills/multi-agent-review ./.claude/skills/
cp -r skills/skills/web-search-fetch ./.claude/skills/
```

## Skills

### roadmap-management

Minimalist project roadmap management based on position-based priority system.

**Use Cases:**
- Project management for solo developers and small teams
- Quick task capture and organization
- Simple workflow without complex priority scoring

**Features:**
- 📥 **Inbox**: Quick capture for ideas and tasks
- 🟢 **Doing**: Current work (limit 2-3 items)
- 🟡 **Next Up**: Manually ordered todo list
- ⚪ **Backlog**: Future tasks
- 📔 **Done**: Recent completions (last 5 items)
- 📜 **CHANGELOG.md**: Full completion history with dates and commits

**Usage:**
```
"Create a roadmap for the current project"
"Add this bug to roadmap"
"Update roadmap, mark feature as complete"
"Archive completed tasks to CHANGELOG"
```

**Details:** See [skills/roadmap-management](./skills/roadmap-management)

### iterative-code-review

Isolated sub-agents perform code review, optional fixes, and independent verification while the development session receives only compact results.

**Use Cases:**
- Automated quality gate after finishing a feature or fix
- Catch bugs, security issues, and reliability problems before merging
- One-line invocation selects review-only or review-and-fix and verifies every fix

**Features:**
- 🤖 **Dynamic sub-agent concurrency**: Covers requirements, correctness, edge cases, security, quality, tests, and runtime evidence
- 🔁 **Verification-driven loop**: Re-freezes the complete diff after fixes, with an 8-iteration upper bound
- 🧹 **Thin main session**: Diff, detailed findings, fix work, and logs move through Git-internal artifacts
- 🎯 **Complete scope**: Includes branch commits, staged, unstaged, and untracked files
- 💣 **Blast-radius guard**: High-impact fixes are never auto-applied; the report points to a separate explicit implementation task
- 📋 **Evidence-backed report**: Records commands, exit codes, unverifiable requirements, residual risk, and conditional merge advice

**Usage:**
```
"Do a code review using iterative-code-review skill"
"Use iterative-code-review for review fix iteration"
"review and fix my changes"
```

**Details:** See [skills/iterative-code-review](./skills/iterative-code-review)

### deploy-caddy-reverse-proxy

Automatically deploy Caddy reverse proxy on remote servers with SSL certificate and systemd service configuration.

**Use Cases:**
- Configure reverse proxy for local web services
- Automatically obtain and manage Let's Encrypt SSL certificates
- Set up systemd service with auto-start on boot
- Proxy HTTP/WebSocket traffic

**Features:**
- 🔒 **Automatic SSL**: Let's Encrypt certificate acquisition and auto-renewal
- 🔄 **Reverse Proxy**: Proxy HTTP/WebSocket traffic to local services
- ⚙️ **Systemd Integration**: Auto-start and crash recovery
- 🎯 **Smart Detection**: Automatically detect system environment and choose optimal configuration
- 📋 **Interactive Configuration**: Collect deployment parameters through Q&A
- ✅ **Deployment Verification**: Automatically verify certificates, ports, and HTTPS access

**Usage:**
```
"Deploy caddy reverse proxy"
"Setup caddy for my web service"
"Configure caddy with SSL"
```

**Details:** See [skills/deploy-caddy-reverse-proxy](./skills/deploy-caddy-reverse-proxy)

### web-search-fetch

Web search and URL fetch for AI agents. The search backend is configurable and invisible to the caller; fetching uses plain HTTP plus a local HTML-to-Markdown converter with zero dependencies.

**Use Cases:**
- Search the web, find URLs, research a topic
- Read/fetch/summarize a webpage as clean Markdown
- Use Brave or a self-hosted RustXNG instance without changing how the skill is invoked

**Features:**
- 🔍 **Search**: NDJSON output with `{url, title, snippet}` per result, `--limit` support
- 📄 **Fetch**: local stdlib-only HTML-to-Markdown converter; by default only the main article content is kept (nav, share links, related lists dropped), `--full` for the whole page, relative URLs resolved
- 🔌 **Provider layer**: Brave keys take priority over `RUSTXNG_URL`; missing keys or Brave HTTP 402/429 use RustXNG, without combining results
- 🗂️ **`.env` auto-load**: reads `BRAVE_API_KEY` (legacy alias: `WEBSEARCH_API_KEY`), `RUSTXNG_URL` and optional `RUSTXNG_TOKEN` from `.env` in CWD
- ⚠️ **JS-page detection**: near-empty extractions warn and point to the agent-browser skill

**Usage:**
```
"Search the web for the latest Python 3.13 release notes"
"Fetch https://docs.example.com/api and summarize it"
```

**Details:** See [skills/web-search-fetch](./skills/web-search-fetch)

### repo-deploy-capture

Capture a verified deployment workflow into project documentation or memory after a successful deploy.

**Use Cases:**
- Record the exact deploy path that just worked
- Preserve health checks, smoke checks, and rollback commands
- Document deployment pitfalls without leaking secrets

**Features:**
- 📋 **Operational capture**: Focuses on commands, directories, checks, and expected success signals
- 🔐 **Sensitive detail scrubbing**: Keeps secrets and private infrastructure out of reusable notes
- 🎯 **Single source of truth**: Prefers one authoritative deployment document over scattered notes

**Usage:**
```
"Capture the deployment workflow we just used"
"Record these deploy steps for next time"
"Save the correct server update procedure in project docs"
```

**Details:** See [skills/repo-deploy-capture](./skills/repo-deploy-capture)

### prod-readiness-audit

Audit and harden a project before production release, then fix issues found where safe.

**Use Cases:**
- Final pre-launch project audit
- Responsive, light/dark theme, SEO, and performance cleanup
- Security, tests, deployment readiness, and production smoke validation

**Features:**
- 🧭 **Structured audit plan**: Baseline, UX completeness, responsive, theme, SEO, performance, security, deployment
- 🛠️ **Fix-oriented workflow**: Fixes concrete issues instead of only reporting them
- ✅ **Verification discipline**: Requires tests, builds, browser checks, Lighthouse, or smoke checks when feasible

**Usage:**
```
"Audit this project before production deployment"
"Handle responsiveness, dark mode, SEO, performance, and security before launch"
"Check whether this project is ready to deploy and fix blockers"
```

**Details:** See [skills/prod-readiness-audit](./skills/prod-readiness-audit)

### multi-agent-review

Configurable multi-model code review workflow using local Claude Code or Codex CLI processes.

**Use Cases:**
- Review uncommitted changes or a feature branch before commit/merge
- Compare independent model findings and synthesize a human-checkable summary
- Fix selected issues with one model and verify them with another
- Use only the review/summary stages, then let the original development session or a human apply fixes

**Features:**
- 🤖 **3 configured review models**: Runs the first three `review_models` independently
- 🧾 **Runner-managed artifacts**: Captures final stdout into `.review-forge/artifacts/<feature>/reviews/`; logs go to `logs/`
- 🧹 **Main session isolation**: Large prompts and diffs stay in ignored `.review-forge/runs/` files, not the development chat
- ✋ **Human gate**: Stops after `summary.md`; the user checks which issues are worth fixing
- 🧩 **Partial workflow**: Review-only, external/manual fix, verify-only-after-fix, or full review→fix→verify are all supported
- 🛠️ **Fix / verify split**: Uses configured `fix_model` and independent `verify_model`
- 🔐 **Single local workspace**: Stores config, runtime prompts, and review artifacts under ignored `.review-forge/`
- 🧷 **First-run config gate**: `init` creates `config_ready: false`; review/fix commands refuse to run until the user confirms model settings
- 🔌 **Optional connectivity check**: `check-config` tests configured role models before the real workflow starts
- 🧭 **Scope inference**: Defaults to working diff on `main`/`master`, or branch-vs-main review on feature branches

**Usage:**
```
"Use multi-agent-review to review my uncommitted changes"
"Run multi-agent-review against origin/main"
"Use multi-agent-review to review this branch"
"Use multi-agent-review, then stop after summary so I can choose what to fix"
"Use multi-agent-review only to produce a review summary"
```

**Details:** See [skills/multi-agent-review](./skills/multi-agent-review)

### Verification

After installation, test the skill in Claude Code:

```
"Create a roadmap for the current project"
```

If Claude starts executing the operation, the installation was successful.

### Supported AI Agents

| Agent | Project Path | Global Path |
|-------|--------------|-------------|
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| Cursor | `.cursor/skills/` | `~/.cursor/skills/` |
| Windsurf | `.windsurf/skills/` | `~/.codeium/windsurf/skills/` |
| Cline | `.cline/skills/` | `~/.cline/skills/` |
| OpenCode | `.opencode/skills/` | `~/.config/opencode/skills/` |
| GitHub Copilot | `.github/skills/` | `~/.copilot/skills/` |

See [skills documentation](https://github.com/vercel-labs/skills#available-agents) for more supported agents.

### Global vs Local Installation

- **Global install** (`~/.claude/skills/`): Available in all projects
- **Local install** (`./.claude/skills/`): Project-specific, takes priority

## Update & Uninstall

### Update Skills

```bash
# Reinstall to update
npx skills add ichuan/skills --skill roadmap-management
npx skills add ichuan/skills --skill iterative-code-review
npx skills add ichuan/skills --skill repo-deploy-capture
npx skills add ichuan/skills --skill prod-readiness-audit
npx skills add ichuan/skills --skill multi-agent-review
npx skills add ichuan/skills --skill web-search-fetch
```

### Uninstall Skills

```bash
# Global uninstall
rm -rf ~/.claude/skills/roadmap-management
rm -rf ~/.claude/skills/iterative-code-review
rm -rf ~/.claude/skills/deploy-caddy-reverse-proxy
rm -rf ~/.claude/skills/repo-deploy-capture
rm -rf ~/.claude/skills/prod-readiness-audit
rm -rf ~/.claude/skills/multi-agent-review
rm -rf ~/.claude/skills/web-search-fetch

# Local uninstall
rm -rf ./.claude/skills/roadmap-management
rm -rf ./.claude/skills/iterative-code-review
rm -rf ./.claude/skills/deploy-caddy-reverse-proxy
rm -rf ./.claude/skills/repo-deploy-capture
rm -rf ./.claude/skills/prod-readiness-audit
rm -rf ./.claude/skills/multi-agent-review
rm -rf ./.claude/skills/web-search-fetch
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Links

- [Agent Skills Specification](https://github.com/anthropics/skills)
- [skills Tool](https://github.com/vercel-labs/skills)
- [Claude Code Documentation](https://github.com/anthropics/claude-code)
