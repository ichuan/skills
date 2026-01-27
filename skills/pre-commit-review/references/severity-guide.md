# Issue Severity Classification Guide

## 🔴 Critical (Must Fix Before Commit)

Issues that can cause:
- **Security vulnerabilities**: Exposed credentials, SQL injection, XSS, authentication bypass
- **Data loss or corruption**: Unhandled database errors, missing transactions
- **System crashes**: Null pointer exceptions, unhandled errors in critical paths
- **Production outages**: Breaking changes without migration, API contract violations

**Action**: Block commit until fixed

**Examples**:
- Hardcoded AWS credentials in source code
- SQL query using string concatenation with user input
- Missing error handling in payment processing
- Deleting production data without confirmation

## 🟡 Warning (Should Fix Before Commit)

Issues that can cause:
- **Performance degradation**: N+1 queries, missing indexes, inefficient algorithms
- **Maintainability problems**: High complexity, code duplication, unclear naming
- **Potential bugs**: Missing null checks, race conditions, improper error handling
- **Technical debt**: Deprecated APIs, outdated dependencies

**Action**: Fix if possible, or create issue to track

**Examples**:
- Loading 10,000 records without pagination
- Three identical functions with minor variations
- Variable named `data` or `tmp`
- Using a library with known vulnerabilities

## 🔵 Info (Nice to Fix)

Issues that affect:
- **Code style**: Formatting, naming conventions, comment quality
- **Minor optimizations**: Caching opportunities, small performance wins
- **Documentation**: Missing JSDoc, outdated comments
- **Suggestions**: Alternative approaches, best practice recommendations

**Action**: Optional fix, helps improve code quality

**Examples**:
- Inconsistent indentation
- Missing docstring for public function
- Could use `const` instead of `let`
- Long function could be split for readability

## Triage Decision Tree

```
Does the issue:
├─ Create security risk? ────────────────────────────→ 🔴 Critical
├─ Cause data loss/corruption? ──────────────────────→ 🔴 Critical
├─ Crash the system? ────────────────────────────────→ 🔴 Critical
├─ Break production? ────────────────────────────────→ 🔴 Critical
├─ Cause performance problems? ──────────────────────→ 🟡 Warning
├─ Create maintenance burden? ───────────────────────→ 🟡 Warning
├─ Potential for bugs? ──────────────────────────────→ 🟡 Warning
└─ Style/documentation issue? ───────────────────────→ 🔵 Info
```
