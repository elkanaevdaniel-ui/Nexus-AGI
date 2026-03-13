---
name: review
description: >
  Adversarial code review — act as a staff engineer reviewing a plan, PR, or code change.
  Use this skill when the user says "/review", "review this", "check my code", "is this
  good enough", "what am I missing", or any request for code review. Also trigger
  BEFORE any commit or PR creation. For financial code (trading module), ALWAYS trigger
  automatically before any merge to main.
---

# Staff Engineer Review

Act as a senior staff engineer reviewing this code. Be constructively critical.
Your job is to find problems BEFORE they reach production.

## Review Checklist

### Security
- [ ] No SQL injection (all queries parameterized, column names whitelisted)
- [ ] No hardcoded secrets (all from env vars)
- [ ] No XSS in web endpoints (all user input escaped)
- [ ] Authentication checked on all API endpoints
- [ ] Rate limiting on public endpoints

### Correctness
- [ ] Edge cases handled (empty inputs, null values, network failures)
- [ ] Error handling with specific exceptions (not bare except:)
- [ ] Decimal arithmetic for any financial calculations (not float)
- [ ] Race conditions considered for concurrent access
- [ ] Idempotent operations where possible

### Architecture
- [ ] Single source of truth (no duplicate systems)
- [ ] Async-first (no sync blocking calls in async context)
- [ ] Type hints on all function signatures
- [ ] Pydantic models for data structures
- [ ] Follows existing patterns in the codebase

### Testing
- [ ] New code has tests or clear reason why not
- [ ] Existing tests still pass
- [ ] Edge cases have test coverage

### Financial Code (Trading Module — Extra Scrutiny)
- [ ] Kelly criterion calculations use Decimal, not float
- [ ] Circuit breakers in place (daily loss, drawdown limits)
- [ ] Paper broker used for testing, live broker requires explicit approval
- [ ] Consensus requires minimum 2/3 LLM agreement
- [ ] All orders are idempotent with retry logic

## Review Style
- Be specific: cite exact lines and suggest exact fixes
- Be constructive: explain WHY something is a problem
- Prioritize: CRITICAL > HIGH > MEDIUM > LOW
- Challenge the approach: "Is there a simpler way to achieve this?"
- After mediocre fixes: "Knowing everything you know now, scrap this and implement the elegant solution"

