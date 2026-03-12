# Python Security Rules

Extends: `../common/security.md`
Applies to: `**/*.py`

## SQL Injection Prevention
```python
# GOOD — parameterized query
result = await session.execute(
    select(Lead).where(Lead.domain == domain)
)

# BAD — f-string in SQL
result = await session.execute(f"SELECT * FROM leads WHERE domain = '{domain}'")
```

## Command Injection Prevention
```python
# GOOD — subprocess with list args
import subprocess
subprocess.run(["git", "log", "--oneline"], check=True)

# BAD — shell=True with user input
subprocess.call(f"git log {user_input}", shell=True)
```

## Dependency Audit
```bash
pip audit          # Check for known vulnerabilities
pip check          # Verify dependency compatibility
```

## FastAPI Security
- Always use `Depends()` for auth on protected endpoints
- Validate request bodies with Pydantic (strict=True where needed)
- Set CORS origins explicitly, never use `"*"` in production
- Rate limit with slowapi or similar on login/sensitive endpoints

## Secrets
- Load from `os.environ` or Pydantic `BaseSettings`
- Never log secrets or include in error messages
- Use `.env` file for local dev (auto-restored from env-restore.b64)
