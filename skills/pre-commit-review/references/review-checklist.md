# Code Review Checklist

## Security

- [ ] No hardcoded credentials, API keys, or secrets
- [ ] No SQL injection vulnerabilities
- [ ] No XSS vulnerabilities
- [ ] No command injection vulnerabilities
- [ ] Input validation for user-provided data
- [ ] Proper authentication and authorization checks
- [ ] Sensitive data is encrypted (passwords, PII)
- [ ] No unsafe deserialization
- [ ] CORS configured correctly
- [ ] Rate limiting for public APIs

## Performance

- [ ] No N+1 query problems
- [ ] Database queries use proper indexes
- [ ] No unnecessary synchronous operations
- [ ] Large datasets paginated or streamed
- [ ] Caching implemented where appropriate
- [ ] No memory leaks (unclosed connections, event listeners)
- [ ] Efficient algorithms (avoid O(n²) when possible)
- [ ] Images/assets optimized
- [ ] Lazy loading implemented for heavy resources

## Code Quality

- [ ] Functions/methods have single responsibility
- [ ] No code duplication (DRY principle)
- [ ] Clear and meaningful variable/function names
- [ ] Magic numbers replaced with named constants
- [ ] Complex logic has explanatory comments
- [ ] No commented-out code blocks
- [ ] No debug console.log/print statements
- [ ] Error messages are user-friendly
- [ ] Code follows project style conventions

## Error Handling

- [ ] All error cases handled appropriately
- [ ] No silent failures (errors logged or reported)
- [ ] Proper error types used
- [ ] User-facing errors are informative
- [ ] Cleanup in finally blocks or defer statements
- [ ] No catch-all handlers hiding real issues
- [ ] Database transactions rolled back on error
- [ ] Proper HTTP status codes returned

## Testing & Reliability

- [ ] Edge cases considered
- [ ] Null/undefined checks where needed
- [ ] Race conditions handled
- [ ] Thread safety for concurrent code
- [ ] Proper cleanup of resources
- [ ] Backwards compatibility maintained
- [ ] Breaking changes documented
- [ ] Migration scripts for database changes

## Best Practices

- [ ] REST API follows conventions (verbs, status codes)
- [ ] GraphQL schema properly typed
- [ ] Dependencies up to date and necessary
- [ ] No deprecated APIs used
- [ ] Proper logging levels (debug, info, warn, error)
- [ ] Configuration externalized (not hardcoded)
- [ ] Feature flags for risky changes
- [ ] Documentation updated for public APIs
