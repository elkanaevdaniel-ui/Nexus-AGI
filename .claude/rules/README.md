# Rules

Layered coding standards for the NEXUS AGI platform.

## Structure

```
rules/
├── common/              # Language-agnostic rules (apply everywhere)
│   ├── coding-style.md  # File org, functions, naming, immutability
│   ├── testing.md       # TDD workflow, coverage requirements, edge cases
│   ├── security.md      # Secret management, injection prevention, auth
│   ├── git-workflow.md  # Commits, PRs, branch strategy, safety
│   ├── performance.md   # Model selection, context management, DB/API perf
│   └── patterns.md      # Backend/frontend/data design patterns
├── python/              # Python-specific extensions
│   ├── coding-style.md  # PEP 8, type hints, async, NEXUS conventions
│   ├── patterns.md      # Protocol, dataclasses, FastAPI, LangGraph
│   ├── testing.md       # pytest, fixtures, async testing
│   └── security.md      # SQL injection, command injection, FastAPI security
└── typescript/          # TypeScript-specific extensions
    ├── coding-style.md  # Strict mode, no-any, Zod, Next.js conventions
    ├── patterns.md      # API response format, hooks, server components
    ├── testing.md       # Jest/Vitest, Playwright, component testing
    └── security.md      # XSS, input validation, CORS, env vars
```

## Override Hierarchy

Language-specific rules supersede common rules when idioms diverge.
Each language file references its common counterpart via `Extends:` header.

## Rules vs Skills

- **Rules** = WHAT to do (standards, conventions, requirements)
- **Skills** = HOW to do it (step-by-step workflows, templates)
