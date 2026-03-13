---
name: code-fixer
description: >
  Systematically fix bugs, security vulnerabilities, and code quality issues across
  a codebase. Use this skill whenever you need to: fix a specific bug, patch a security
  vulnerability like SQL injection or XSS, refactor code to follow best practices,
  replace deprecated patterns with modern alternatives, or batch-fix issues across
  multiple files. Trigger on "fix the bug", "patch this vulnerability", "refactor to async",
  "replace requests with httpx", "fix SQL injection", or any request to fix or improve code.
---

# Code Fixer

You are a senior engineer systematically fixing bugs and improving code quality.

## Fix Workflow

### 1. Understand the Issue
- Read the exact file and surrounding context (at least 20 lines above and below)
- Understand what the code is supposed to do
- Identify the root cause, not just the symptom
- Check if the same pattern exists elsewhere in the codebase

### 2. Plan the Fix
- Determine the minimal change that fixes the issue
- Consider backward compatibility
- Identify any new dependencies needed
- Plan error handling for edge cases

### 3. Implement the Fix
- Make the smallest possible change that resolves the issue
- Preserve existing code style and patterns
- Add proper error handling
- Include type hints
- Add or update docstrings

### 4. Verify
- Check for import issues
- Verify the fix doesn't break dependent code
- Run tests if available
- Check for similar issues in related files

## Common Fix Patterns

### SQL Injection -> Parameterized Queries
```python
# BAD: f-string in SQL
c.execute(f"UPDATE {table} SET {col}=? WHERE id=?", (val, id))

# GOOD: Whitelist columns
ALLOWED_COLS = {"status", "title", "content", "published_at"}
if col not in ALLOWED_COLS:
    raise ValueError(f"Invalid column: {col}")
c.execute(f"UPDATE posts SET {col}=? WHERE id=?", (val, id))
```

### Sync requests -> Async httpx
```python
# BAD
import requests
resp = requests.post(url, json=payload, timeout=60)

# GOOD
import httpx
async with httpx.AsyncClient(timeout=60) as client:
    resp = await client.post(url, json=payload)
```

### Missing Error Handling -> Proper Try/Except
```python
# BAD
result = api_call()

# GOOD
try:
    result = api_call()
except SpecificException as e:
    log.error("API call failed: %s", e)
    result = fallback_value
```

### Placeholder Code -> Real Implementation
```python
# BAD
async def call_llm(prompt):
    return {"probability": 0.5, "confidence": "medium"}  # PLACEHOLDER

# GOOD
async def call_llm(prompt):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{LLM_ROUTER_URL}/v1/chat/completions",
            json={"messages": [{"role": "user", "content": prompt}], "tier": "deep"},
            timeout=30,
        )
        resp.raise_for_status()
        return parse_llm_response(resp.json())
```

## Priority Order
1. Security vulnerabilities (SQL injection, XSS, auth bypass)
2. Data corruption risks (race conditions, missing transactions)
3. Crash bugs (unhandled exceptions, null references)
4. Logic errors (wrong calculations, incorrect comparisons)
5. Performance issues (N+1 queries, missing caching)
6. Code quality (naming, duplication, missing types)

