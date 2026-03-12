# Security Rules — Universal

## Before ANY Commit
- [ ] No hardcoded secrets (API keys, passwords, tokens)
- [ ] All user inputs validated
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (sanitized output)
- [ ] CSRF protection enabled
- [ ] Auth/authorization verified on new endpoints
- [ ] Rate limiting on sensitive endpoints
- [ ] Error messages don't leak internals

## Secret Management
- NEVER hardcode secrets in source code
- ALWAYS use environment variables
- Validate required secrets at startup
- Rotate any secrets that may have been exposed
- All keys stored in `env-restore.b64` — never create per-service .env files

## Injection Prevention
- SQL: Use parameterized queries, NEVER f-strings in SQL
- Command: No `os.system()`, no `subprocess.call(shell=True)` with user input
- XSS: No `dangerouslySetInnerHTML` with unsanitized data
- Template: Sanitize user input before LLM prompts

## Authentication & Authorization
- Missing auth on new endpoints = CRITICAL vulnerability
- Always check: can user A access user B's data?
- Validate JWT signatures and expiration
- Rate limit login and API key endpoints

## Data Exposure
- Never include passwords or tokens in API responses
- Verbose errors → development only, generic errors → production
- Never log PII, tokens, or request bodies with secrets
- CORS: whitelist specific origins, never `*` in production

## Security Incident Response
1. STOP immediately
2. Use **security-auditor** agent
3. Fix CRITICAL issues before continuing
4. Rotate any exposed secrets
5. Review entire codebase for similar issues
