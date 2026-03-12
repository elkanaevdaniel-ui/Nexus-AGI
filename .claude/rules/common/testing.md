# Testing Rules — Universal

## Coverage Requirements
- **Minimum**: 80% across branches, functions, lines, statements
- **100% required for**: Auth logic, security-critical code, financial calculations

## Test Types Required
| Type | What to Test | When |
|------|-------------|------|
| **Unit** | Individual functions in isolation | Always |
| **Integration** | API endpoints, DB operations | Always |
| **E2E** | Critical user flows | Critical paths |

## TDD Workflow (Mandatory for New Features)
1. Write test first (RED) — must fail
2. Write minimal implementation (GREEN)
3. Refactor (IMPROVE) — tests stay green
4. Verify 80%+ coverage

## Edge Cases to Always Test
1. Null/undefined/None input
2. Empty arrays/strings/collections
3. Invalid types and malformed data
4. Boundary values (min, max, zero, negative)
5. Error paths (network failures, DB errors, timeouts)
6. Concurrent operations and race conditions
7. Special characters (Unicode, SQL injection chars, XSS payloads)

## Anti-Patterns to Avoid
- Testing implementation details instead of behavior
- Shared state between tests
- Meaningless assertions that always pass
- Not mocking external dependencies
- Skipping error path tests
- Tests that depend on execution order

## When Tests Fail
1. Use the **tdd-guide** agent
2. Verify tests are properly isolated
3. Check mock implementations
4. Fix implementation, NOT the test (unless test logic is wrong)
