# Code Review Checklist

各 reviewer sub-agent 可引用此文件中对应的维度检查项，补充其 prompt 中列出的核心检查点。

---

## Security

- [ ] No hardcoded credentials, API keys, or secrets in source code
- [ ] No SQL injection vulnerabilities (parameterized queries used)
- [ ] No XSS vulnerabilities (user output properly escaped)
- [ ] No command injection vulnerabilities (user input not passed to shell)
- [ ] Input validation for all user-provided data at system boundaries
- [ ] Proper authentication and authorization checks on every protected route
- [ ] Sensitive data encrypted at rest (passwords hashed, PII not stored in plaintext)
- [ ] No unsafe deserialization of user-controlled data
- [ ] CORS configured correctly (not `*` on credentialed endpoints)
- [ ] Rate limiting in place for public-facing APIs
- [ ] No path traversal risk (user-supplied paths sanitized / restricted)

## Performance

- [ ] No N+1 query problems (batch or join instead of looping DB calls)
- [ ] Database queries target indexed columns (large table scans flagged)
- [ ] No unnecessary synchronous / blocking operations on async paths
- [ ] Large datasets paginated or streamed (not loaded entirely into memory)
- [ ] No memory leaks (file handles, DB connections, event listeners closed)
- [ ] Efficient algorithms — avoid O(n²) when O(n log n) or better is feasible
- [ ] Loop-invariant computations hoisted out of loops
- [ ] Heavy or repeated resources cached where appropriate

## Correctness & Reliability

- [ ] All error cases handled — no silent swallowing of exceptions
- [ ] No catch-all handlers that hide real errors (`except Exception: pass`)
- [ ] Resources cleaned up in `finally` / `defer` / `using` blocks
- [ ] Database operations wrapped in transactions; rolled back on error
- [ ] Proper HTTP status codes returned (errors don't return 200)
- [ ] External calls have timeouts and retry logic where appropriate
- [ ] Null / None / undefined checks where values can be absent
- [ ] Race conditions and thread safety considered for shared state
- [ ] Loop / recursion termination conditions are correct
- [ ] Off-by-one errors checked (index bounds, range endpoints)
- [ ] No debug output (console.log / print / pprint) left in committed code

## Code Quality & Best Practices

- [ ] Functions / methods have single responsibility (not doing too many things)
- [ ] No duplicated code blocks — DRY principle applied
- [ ] Magic numbers and magic strings extracted to named constants
- [ ] Variable / function names are clear and meaningful (avoid `data`, `tmp`, `flag`)
- [ ] No commented-out code blocks committed
- [ ] Complex or non-obvious logic has a "Why" comment explaining intent
- [ ] No deprecated APIs used
- [ ] No dependencies with known critical vulnerabilities introduced
- [ ] Configuration values externalized (not hardcoded — use env vars or config files)
- [ ] Public API documentation updated when signatures change
- [ ] REST endpoints follow project conventions (verbs, status codes, URL structure)
- [ ] Logging uses appropriate levels (debug / info / warn / error); no sensitive data logged
