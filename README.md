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
npx skills add ichuan/skills --skill searxng-search
npx skills add ichuan/skills --skill crawl4ai-fetch
npx skills add ichuan/skills --skill repo-deploy-capture
npx skills add ichuan/skills --skill prod-readiness-audit
npx skills add ichuan/skills --skill multi-agent-review

# Install globally (available in all projects)
npx skills add ichuan/skills --skill roadmap-management --global
npx skills add ichuan/skills --skill iterative-code-review --global
npx skills add ichuan/skills --skill deploy-caddy-reverse-proxy --global
npx skills add ichuan/skills --skill searxng-search --global
npx skills add ichuan/skills --skill crawl4ai-fetch --global
npx skills add ichuan/skills --skill repo-deploy-capture --global
npx skills add ichuan/skills --skill prod-readiness-audit --global
npx skills add ichuan/skills --skill multi-agent-review --global
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/ichuan/skills.git

# Copy to global skills directory
cp -r skills/skills/roadmap-management ~/.claude/skills/
cp -r skills/skills/iterative-code-review ~/.claude/skills/
cp -r skills/skills/deploy-caddy-reverse-proxy ~/.claude/skills/
cp -r skills/skills/searxng-search ~/.claude/skills/
cp -r skills/skills/crawl4ai-fetch ~/.claude/skills/
cp -r skills/skills/repo-deploy-capture ~/.claude/skills/
cp -r skills/skills/prod-readiness-audit ~/.claude/skills/
cp -r skills/skills/multi-agent-review ~/.claude/skills/

# Or copy to project-local directory
mkdir -p ./.claude/skills
cp -r skills/skills/roadmap-management ./.claude/skills/
cp -r skills/skills/iterative-code-review ./.claude/skills/
cp -r skills/skills/deploy-caddy-reverse-proxy ./.claude/skills/
cp -r skills/skills/searxng-search ./.claude/skills/
cp -r skills/skills/crawl4ai-fetch ./.claude/skills/
cp -r skills/skills/repo-deploy-capture ./.claude/skills/
cp -r skills/skills/prod-readiness-audit ./.claude/skills/
cp -r skills/skills/multi-agent-review ./.claude/skills/
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

Multi-agent iterative code review with auto-fix, running until convergence.

**Use Cases:**
- Automated quality gate after finishing a feature or fix
- Catch bugs, security issues, and reliability problems before merging
- Self-healing loop: review → fix → re-review until no issues remain

**Features:**
- 🤖 **5 parallel sub-agents**: Correctness, Security, Performance, Reliability, Code Quality — each reviews independently in a fresh context
- 🔁 **Iterative loop**: Fixes trigger a new review round; stops when converged or `max_iterations` reached
- 🧹 **Main session isolation**: Sub-agents fetch their own `git diff`; main session context stays clean
- 🎯 **Noise filter**: Only Critical / High issues with Confidence ≥ 0.70 are auto-fixed
- 💣 **Blast Radius guard**: High-impact fixes (public API changes) require elevated confidence
- 📋 **Structured final report**: Fixed / skipped issues table, residual risk, merge recommendation

**Usage:**
```
"Do a code review using iterative-code-review skill"
"review and fix my changes"
"iterative code review, max_iterations=5"
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

### searxng-search

Web search via a self-hosted [SearXNG](https://github.com/searxng/searxng) aggregation server.

**Use Cases:**
- Search the web from within AI agents
- Research topics, find URLs, look up information online
- Self-hosted, privacy-respecting alternative to commercial search APIs

**Features:**
- 🔍 **NDJSON output**: Structured `{url, title, snippet}` per result line
- 🔑 **Bearer auth support**: Optional token for protected instances
- 📄 **Pagination**: `--page` / `--limit` flags for deeper result sets
- 🗂️ **`.env` auto-load**: Reads `SEARXNG_URL` / `SEARXNG_TOKEN` from `.env` in CWD if not set in environment

**Usage:**
```
"Search the web for the latest Python 3.13 release notes"
"Find documentation for the Caddy web server"
"Look up recent news about LLM benchmarks"
```

**Details:** See [skills/searxng-search](./skills/searxng-search)

#### Deploying SearXNG with Caddy Bearer Auth

SearXNG does not ship with built-in authentication. The following Caddy snippet adds a simple Bearer token gate in front of your instance:

```caddy
# Caddyfile

(auth_bearer) {
    handle {
        @valid_token header Authorization "Bearer {args[0]}"
        route @valid_token {
            reverse_proxy {args[1]} {
                header_up Host {http.reverse_proxy.upstream.hostport}
            }
        }

        @invalid_token not header Authorization "Bearer {args[0]}"
        respond @invalid_token "Unauthorized" 401
    }
}

search.example.com {
    encode gzip
    import auth_bearer YOUR_SECRET_TOKEN http://127.0.0.1:8001
}
```

Replace `search.example.com`, `YOUR_SECRET_TOKEN`, and `http://127.0.0.1:8001` (the address SearXNG listens on) with your own values. Caddy will automatically provision a Let's Encrypt TLS certificate for the domain.

Then configure the skill:

```
# .env (project root)
SEARXNG_URL=https://search.example.com
SEARXNG_TOKEN=YOUR_SECRET_TOKEN
```

### crawl4ai-fetch

Fetch any URL and convert it to clean Markdown via a self-hosted [crawl4ai](https://github.com/unclecode/crawl4ai) server.

**Use Cases:**
- Read and summarize a webpage for an LLM
- Extract article or documentation content as Markdown
- Crawl JavaScript-rendered pages that plain HTTP clients can't read

**Features:**
- 📄 **Markdown output**: Clean, LLM-ready Markdown from any URL
- 🎯 **Filter modes**: `fit` (smart), `raw` (full page), `bm25` (query-relevant)
- 🔑 **Bearer auth support**: Optional token for protected instances
- 🗂️ **`.env` auto-load**: Reads `CRAWL4AI_URL` / `CRAWL4AI_TOKEN` from `.env` in CWD if not set in environment

**Usage:**
```
"Fetch https://docs.example.com/api and summarize it"
"Get the content of this news article: https://..."
"Read this page and answer my question about it"
```

**Details:** See [skills/crawl4ai-fetch](./skills/crawl4ai-fetch)

#### Deploying crawl4ai with Caddy Bearer Auth

Start the crawl4ai Docker container:

```bash
docker stop crawl4ai
docker run --rm -itd \
  -p 8002:11235 \
  --name crawl4ai \
  --shm-size=1g \
  unclecode/crawl4ai:latest
```

Then add a Caddy site block using the same `auth_bearer` snippet as SearXNG (see above):

```caddy
crawl.example.com {
    encode gzip
    import auth_bearer YOUR_SECRET_TOKEN http://127.0.0.1:8002
}
```

Configure the skill:

```
# .env (project root)
CRAWL4AI_URL=https://crawl.example.com
CRAWL4AI_TOKEN=YOUR_SECRET_TOKEN
```

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

**Features:**
- 🤖 **3 configured review models**: Runs the first three `review_models` independently
- 🧾 **Runner-managed artifacts**: Captures final stdout into `.review-forge/artifacts/<feature>/reviews/`; logs go to `logs/`
- 🧹 **Main session isolation**: Large prompts and diffs stay in ignored `.review-forge/runs/` files, not the development chat
- ✋ **Human gate**: Stops after `summary.md`; the user checks which issues are worth fixing
- 🛠️ **Fix / verify split**: Uses configured `fix_model` and independent `verify_model`
- 🔐 **Single local workspace**: Stores config, runtime prompts, and review artifacts under ignored `.review-forge/`
- 🧷 **First-run config gate**: `init` creates `config_ready: false`; review/fix commands refuse to run until the user confirms model settings
- 🔌 **Optional connectivity check**: `check-config` tests configured role models before the real workflow starts

**Usage:**
```
"Use multi-agent-review to review my uncommitted changes"
"Run multi-agent-review against origin/main"
"Use multi-agent-review, then stop after summary so I can choose what to fix"
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
npx skills add ichuan/skills --skill searxng-search
npx skills add ichuan/skills --skill crawl4ai-fetch
npx skills add ichuan/skills --skill repo-deploy-capture
npx skills add ichuan/skills --skill prod-readiness-audit
npx skills add ichuan/skills --skill multi-agent-review
```

### Uninstall Skills

```bash
# Global uninstall
rm -rf ~/.claude/skills/roadmap-management
rm -rf ~/.claude/skills/iterative-code-review
rm -rf ~/.claude/skills/deploy-caddy-reverse-proxy
rm -rf ~/.claude/skills/searxng-search
rm -rf ~/.claude/skills/crawl4ai-fetch
rm -rf ~/.claude/skills/repo-deploy-capture
rm -rf ~/.claude/skills/prod-readiness-audit
rm -rf ~/.claude/skills/multi-agent-review

# Local uninstall
rm -rf ./.claude/skills/roadmap-management
rm -rf ./.claude/skills/iterative-code-review
rm -rf ./.claude/skills/deploy-caddy-reverse-proxy
rm -rf ./.claude/skills/searxng-search
rm -rf ./.claude/skills/crawl4ai-fetch
rm -rf ./.claude/skills/repo-deploy-capture
rm -rf ./.claude/skills/prod-readiness-audit
rm -rf ./.claude/skills/multi-agent-review
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Links

- [Agent Skills Specification](https://github.com/anthropics/skills)
- [skills Tool](https://github.com/vercel-labs/skills)
- [Claude Code Documentation](https://github.com/anthropics/claude-code)
