# Git Workflow Rules

## Commit Messages
Format: `<type>: <description>`

**Types**: feat, fix, refactor, docs, test, chore, perf, ci

Examples:
- `feat: add lead scoring pipeline endpoint`
- `fix: handle null campaign status in dashboard`
- `refactor: extract LLM routing to service layer`

## Branch Strategy
- Feature branches from main: `feat/feature-name`
- Bug fix branches: `fix/bug-description`
- Always rebase before merge to keep history clean

## Before Committing
1. Run `git diff` to review all changes
2. Run tests: `pytest` (Python) / `npm test` (TypeScript)
3. Check for secrets: no API keys, passwords, or tokens
4. Stage specific files (not `git add -A`)
5. Write descriptive commit message

## Pull Request Rules
- Review the COMPLETE commit history, not just latest commit
- Run `git diff [base-branch]...HEAD` to see all changes
- Keep PRs under 400 lines when possible
- Title format matches commit types
- Include test plan in PR description

## Safety
- Never force push to main/master
- Never use `--no-verify` to skip hooks
- Always create NEW commits, don't amend published ones
- Investigate before using destructive operations (reset --hard, checkout --)
