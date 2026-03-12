# Python Coding Style

Extends: `../common/coding-style.md`

## Standards
- PEP 8 compliance
- Type hints on ALL public function signatures
- 4-space indentation
- `async/await` for all I/O operations

## Data Structures
- Frozen dataclasses: `@dataclass(frozen=True)` for immutable data
- Pydantic models for API request/response and validation
- NamedTuple for lightweight immutable records
- Never return raw dicts from API endpoints

## Formatting Tools
- **black** — auto-formatting
- **isort** — import organization
- **ruff** — comprehensive linting

## Import Order
1. Standard library
2. Third-party packages
3. Local imports
4. Blank line between each group

## Async Rules
- Use `httpx` (not `requests`) for HTTP calls
- Use SQLAlchemy async sessions (not sync)
- Use `asyncio.gather()` for parallel async operations
- Never call sync I/O in async context

## NEXUS-Specific
- Import from `langchain_core` or `langgraph` — NEVER from `langchain`
- All API routes return Pydantic models
- FastAPI dependency injection for DB sessions and auth
- Environment config from root `.env` — never hardcode
- LLM calls always use fallback chains
