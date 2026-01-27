---
name: pre-commit-review
description: "Comprehensive code review for uncommitted changes before git commit. Use when users want to: (1) Review code changes before committing, (2) Check for security vulnerabilities, bugs, or performance issues, (3) Get feedback on code quality and best practices, (4) Identify issues by severity level. Triggered by phrases like 'review my changes', 'check my code', 'review before commit', 'code review', or similar requests for pre-commit validation."
---

# Pre-Commit Code Review

## Overview

Perform comprehensive code review on uncommitted changes (staged and unstaged) to identify security issues, bugs, performance problems, and code quality concerns before committing. Issues are classified by severity with actionable recommendations.

## Review Workflow

### 1. Gather Changes

Collect all code changes that will be committed:

```bash
# Check repository status (for context only)
git status

# Get staged changes (primary review target)
git diff --cached

# Get unstaged changes (secondary review target)
git diff

# View recent commits for context
git log -3 --oneline
```

**Important**: Git status information (unstaged files, untracked files) is context only, not code issues. Only review the actual code changes in the diff output.

### 2. Analyze Changes

Review the code changes systematically:

1. **Read the diff output** - Understand what changed and why
2. **Identify modified files** - Note file types and their roles
3. **Examine added/deleted lines** - Look for CODE issues (security, bugs, performance, quality)
4. **Consider context** - Review surrounding code when needed using Read tool

**Do not report**: Git staging status, untracked files, or other git metadata as issues. Only analyze code content.

### 3. Apply Review Criteria

Check changes against comprehensive criteria. Load the full checklist when needed:

```
Read references/review-checklist.md
```

**Quick scan areas:**
- Security: Credentials, injection vulnerabilities, authentication
- Performance: Database queries, algorithmic complexity, resource usage
- Code Quality: Naming, duplication, complexity
- Error Handling: Try-catch blocks, edge cases, cleanup
- Best Practices: API conventions, dependency management

### 4. Classify Issues by Severity

Categorize each issue found using this classification:

- **🔴 Critical** - Security vulnerabilities, data loss risks, system crashes, production breaking changes
- **🟡 Warning** - Performance problems, maintainability issues, potential bugs, technical debt
- **🔵 Info** - Code style, minor optimizations, documentation, suggestions

For detailed classification guidance:

```
Read references/severity-guide.md
```

### 5. Present Review Results

Format the review output as follows:

```markdown
## Code Review Summary

**Files Changed**: [number]
**Lines Added**: [number] | **Lines Removed**: [number]

**Note**: [If unstaged changes exist, briefly mention "N files have unstaged changes" as FYI, not as an issue]

---

## 🔴 Critical Issues

### [Issue Title]
**File**: `path/to/file.js:123`
**Problem**: [Clear description of what's wrong]
**Impact**: [What could happen if not fixed]
**Solution**: [Specific fix recommendation]

---

## 🟡 Warnings

### [Issue Title]
**File**: `path/to/file.js:456`
**Problem**: [Description]
**Solution**: [Recommendation]

---

## 🔵 Info

### [Issue Title]
**File**: `path/to/file.js:789`
**Suggestion**: [Improvement idea]

---

## ✅ Recommendation

- **Commit Status**: [Ready to commit / Fix critical issues first / Needs attention]
- **Summary**: [Overall assessment]
```

### 6. Address Critical Issues First

If critical issues (🔴) are found:

1. Explain the severity clearly
2. Offer to fix the issues immediately
3. Re-review after fixes are applied

## Quick Review Mode

For faster reviews of small changes (< 100 lines), use abbreviated checklist:

1. Security: Hardcoded secrets, injection risks
2. Bugs: Null checks, error handling
3. Performance: Obvious inefficiencies
4. Quality: Naming, duplication

## Resources

### references/review-checklist.md
Comprehensive checklist covering security, performance, code quality, error handling, testing, and best practices. Load this for thorough reviews or when unsure what to check.

### references/severity-guide.md
Detailed guide for classifying issues by severity (Critical/Warning/Info) with examples and decision tree. Load this when uncertain about issue priority or to explain severity to users.
