# Personal Skills Collection

A collection of reusable skill sets for AI coding agents like Claude Code, Cursor, and Windsurf.

## Overview

This repository contains Agent Skills that extend AI coding assistants with specialized capabilities. All skills follow the standard Agent Skills specification and can be installed using `npx add-skill`.

## Installation

### Install from GitHub

```bash
# Install all skills
npx add-skill ichuan/skills

# Install a specific skill
npx add-skill ichuan/skills --skill roadmap-management

# Install globally (available in all projects)
npx add-skill ichuan/skills --skill roadmap-management --global
```

### Manual Installation

```bash
# Clone the repository
git clone https://github.com/ichuan/skills.git

# Copy to global skills directory
cp -r skills/skills/roadmap-management ~/.claude/skills/

# Or copy to project-local directory
mkdir -p ./.claude/skills
cp -r skills/skills/roadmap-management ./.claude/skills/
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

See [add-skill documentation](https://github.com/vercel-labs/add-skill#available-agents) for more supported agents.

### Global vs Local Installation

- **Global install** (`~/.claude/skills/`): Available in all projects
- **Local install** (`./.claude/skills/`): Project-specific, takes priority

## Update & Uninstall

### Update Skills

```bash
# Reinstall to update
npx add-skill ichuan/skills --skill roadmap-management
```

### Uninstall Skills

```bash
# Global uninstall
rm -rf ~/.claude/skills/roadmap-management

# Local uninstall
rm -rf ./.claude/skills/roadmap-management
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Links

- [Agent Skills Specification](https://github.com/anthropics/skills)
- [add-skill Tool](https://github.com/vercel-labs/add-skill)
- [Claude Code Documentation](https://github.com/anthropics/claude-code)
