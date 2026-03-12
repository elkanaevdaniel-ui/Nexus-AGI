# Coding Style — Universal Rules

## Immutability
- ALWAYS create new objects, NEVER mutate existing ones
- Use spread operators for updates: `return { ...obj, key: newValue }`
- Use frozen dataclasses in Python: `@dataclass(frozen=True)`

## File Organization
- 200-400 lines per file, 800-line hard maximum
- Organize by feature/domain, not by file type
- High cohesion within files, low coupling between them
- Many small files > few large files

## Functions
- Maximum 50 lines per function
- Maximum 4 levels of nesting
- Single responsibility — one function, one purpose
- Early returns over deep nesting

## Error Handling
- Handle errors explicitly at every level
- User-facing: friendly messages
- Server-side: detailed context in logs
- NEVER silently swallow errors
- Fail fast with clear messages

## Input Validation
- Validate ALL user input at system boundaries
- Use schema-based validation (Pydantic for Python, Zod for TypeScript)
- Never trust external data (API responses, user input, file content)
- Fail fast with clear validation errors

## Naming
- Variables: descriptive, no abbreviations except well-known (id, url, api)
- Functions: verb-first (`getUserById`, `calculate_total`)
- Booleans: prefix with is/has/can/should
- Constants: UPPER_SNAKE_CASE

## Code Quality Checklist
- [ ] Readable and clear naming
- [ ] Functions under 50 lines
- [ ] Files under 800 lines
- [ ] Nesting under 4 levels
- [ ] Proper error handling
- [ ] No hardcoded values (use constants/config)
- [ ] Immutable patterns used
