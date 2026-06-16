You are synthesizing independent AI code review reports.

Feature: {{feature}}

Rules:
- Read the reports below.
- Merge duplicate findings with the same root cause.
- Prioritize issues found by multiple reviewers.
- Do not invent issues that are not supported by a report.
- Do not include chain-of-thought.
- Return only `summary.md` content.

Output format:

# Review Summary

## Selected For Fix

Use unchecked boxes. The user will check the issues to fix.

```markdown
- [ ] `RF-001`
  - severity: high
  - reviewer_agreement: 2/3 (model-a, model-b)
  - files: src/example.ts:42
  - problem: ...
  - evidence: ...
  - suggested_fix: ...
```

## Not Recommended

List low-confidence, low-severity, or likely false-positive findings with short reasons.

Reports:

{{reports}}
