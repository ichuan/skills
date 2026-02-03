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

# Install globally (available in all projects)
npx skills add ichuan/skills --skill roadmap-management --global
npx skills add ichuan/skills --skill pre-commit-review --global
npx skills add ichuan/skills --skill deploy-caddy-reverse-proxy --global
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/ichuan/skills.git

# Copy to global skills directory
cp -r skills/skills/roadmap-management ~/.claude/skills/
cp -r skills/skills/pre-commit-review ~/.claude/skills/
cp -r skills/skills/deploy-caddy-reverse-proxy ~/.claude/skills/

# Or copy to project-local directory
mkdir -p ./.claude/skills
cp -r skills/skills/roadmap-management ./.claude/skills/
cp -r skills/skills/pre-commit-review ./.claude/skills/
cp -r skills/skills/deploy-caddy-reverse-proxy ./.claude/skills/
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
- 📔 **Done**: Completed achievements

**Usage:**
```
"Create a roadmap for the current project"
"Add this bug to roadmap"
"Update roadmap, mark feature as complete"
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

在远程服务器上自动部署 Caddy 反向代理，配置 SSL 证书和 systemd 服务。

**Use Cases:**
- 为本地 web 服务配置反向代理
- 自动获取和管理 Let's Encrypt SSL 证书
- 配置 systemd 服务实现开机自启
- 支持 HTTP/WebSocket 流量代理

**Features:**
- 🔒 **自动 SSL**: Let's Encrypt 证书自动获取和续期
- 🔄 **反向代理**: HTTP/WebSocket 流量代理到本地服务
- ⚙️ **Systemd 集成**: 服务自动启动和崩溃重启
- 🎯 **智能适配**: 自动检测系统环境并选择最佳配置
- 📋 **交互式配置**: 通过问答收集部署参数
- ✅ **部署验证**: 自动检查证书、端口、HTTPS 访问

**Usage:**
```
"Deploy caddy reverse proxy"
"Setup caddy for my web service"
"Configure caddy with SSL"
```

**Details:** See [skills/deploy-caddy-reverse-proxy](./skills/deploy-caddy-reverse-proxy)

## Usage

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
```

### Uninstall Skills

```bash
# Global uninstall
rm -rf ~/.claude/skills/roadmap-management
rm -rf ~/.claude/skills/pre-commit-review
rm -rf ~/.claude/skills/deploy-caddy-reverse-proxy

# Local uninstall
rm -rf ./.claude/skills/roadmap-management
rm -rf ./.claude/skills/pre-commit-review
rm -rf ./.claude/skills/deploy-caddy-reverse-proxy
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Links

- [Agent Skills Specification](https://github.com/anthropics/skills)
- [skills Tool](https://github.com/vercel-labs/skills)
- [Claude Code Documentation](https://github.com/anthropics/claude-code)
