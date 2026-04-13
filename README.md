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
npx skills add ichuan/skills --skill pre-commit-review
npx skills add ichuan/skills --skill deploy-caddy-reverse-proxy
npx skills add ichuan/skills --skill searxng-search

# Install globally (available in all projects)
npx skills add ichuan/skills --skill roadmap-management --global
npx skills add ichuan/skills --skill pre-commit-review --global
npx skills add ichuan/skills --skill deploy-caddy-reverse-proxy --global
npx skills add ichuan/skills --skill searxng-search --global
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/ichuan/skills.git

# Copy to global skills directory
cp -r skills/skills/roadmap-management ~/.claude/skills/
cp -r skills/skills/pre-commit-review ~/.claude/skills/
cp -r skills/skills/deploy-caddy-reverse-proxy ~/.claude/skills/
cp -r skills/skills/searxng-search ~/.claude/skills/

# Or copy to project-local directory
mkdir -p ./.claude/skills
cp -r skills/skills/roadmap-management ./.claude/skills/
cp -r skills/skills/pre-commit-review ./.claude/skills/
cp -r skills/skills/deploy-caddy-reverse-proxy ./.claude/skills/
cp -r skills/skills/searxng-search ./.claude/skills/
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

### pre-commit-review

Comprehensive code review for uncommitted changes before git commit.

**Use Cases:**
- Pre-commit code validation
- Security vulnerability detection
- Performance issue identification
- Code quality assessment

**Features:**
- 🔴 **Critical Issues**: Security vulnerabilities, data loss risks, system crashes
- 🟡 **Warnings**: Performance problems, maintainability issues, potential bugs
- 🔵 **Info**: Code style, optimizations, documentation suggestions
- 📋 **Comprehensive Checklist**: Security, performance, quality, error handling
- 🎯 **Actionable Solutions**: Specific fix recommendations for each issue

**Usage:**
```
"Review my changes before commit"
"Check my code for issues"
"Code review before committing"
```

**Details:** See [skills/pre-commit-review](./skills/pre-commit-review)

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
npx skills add ichuan/skills --skill pre-commit-review
npx skills add ichuan/skills --skill searxng-search
```

### Uninstall Skills

```bash
# Global uninstall
rm -rf ~/.claude/skills/roadmap-management
rm -rf ~/.claude/skills/pre-commit-review
rm -rf ~/.claude/skills/deploy-caddy-reverse-proxy
rm -rf ~/.claude/skills/searxng-search

# Local uninstall
rm -rf ./.claude/skills/roadmap-management
rm -rf ./.claude/skills/pre-commit-review
rm -rf ./.claude/skills/deploy-caddy-reverse-proxy
rm -rf ./.claude/skills/searxng-search
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Links

- [Agent Skills Specification](https://github.com/anthropics/skills)
- [skills Tool](https://github.com/vercel-labs/skills)
- [Claude Code Documentation](https://github.com/anthropics/claude-code)
