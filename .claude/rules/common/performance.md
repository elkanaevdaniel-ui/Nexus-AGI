# Performance Rules

## Model Selection Strategy

### Tier 1: Fast & Cheap (Haiku-class)
- 90% of Sonnet capability at 3x cost savings
- Use for: classification, simple extraction, high-volume operations
- Models: claude-haiku-4-5, gemini-2.5-flash, gpt-4o-mini

### Tier 2: Balanced (Sonnet-class)
- Primary coding model
- Use for: main development, orchestration, complex analysis
- Models: claude-sonnet-4-6, gemini-2.5-pro, gpt-4o

### Tier 3: Deep Reasoning (Opus-class)
- Maximum reasoning capability
- Use for: architecture decisions, complex debugging, research
- Models: claude-opus-4-6, o1-preview

## Context Window Management
- Avoid consuming the final 20% for large refactoring tasks
- Use strategic compaction at natural breakpoints
- Keep under 10 MCP servers enabled per project
- Keep under 80 tools active to prevent context bloat

## Database Performance
- No N+1 queries — use proper JOINs or eager loading
- Index frequently queried columns
- Use async sessions for all DB operations
- Connection pooling with appropriate limits

## API Performance
- Use `httpx` with async for all HTTP calls
- Implement proper timeouts on external API calls
- Use Redis for caching frequently accessed data
- Batch operations where possible

## Frontend Performance
- Server components by default, `"use client"` only when needed
- Lazy load routes and heavy components
- Optimize images (proper sizing, formats, CDN)
- Minimize client-side JavaScript bundle
