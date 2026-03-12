# Design Patterns — Universal

## Backend Patterns

### Repository Pattern
Abstract data access behind a consistent interface:
- `find_all()`, `find_by_id()`, `create()`, `update()`, `delete()`
- Keeps business logic independent of storage

### Service Layer
Separate business logic from API routes:
- Routes are thin — validate input, call service, return response
- Services contain all business logic
- Services are testable without HTTP context

### Middleware Pattern
Request/response processing pipeline:
- Auth middleware validates tokens
- Logging middleware tracks requests
- Error middleware formats responses

### Event-Driven Architecture
For async operations that don't need immediate response:
- Background jobs via Redis queue
- Webhook handlers for external events
- LangGraph state machine for multi-step workflows

## Frontend Patterns

### Component Composition
Build complex UI from simple components:
- Presentational components (pure UI, no state)
- Container components (data fetching, state management)
- Custom hooks for reusable stateful logic

### Server Components (Next.js)
- Default to server components
- `"use client"` only for interactivity (onClick, useState, useEffect)
- Fetch data in server components, pass as props

### API Response Format
Consistent response structure:
```typescript
interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  metadata?: Record<string, unknown>;
}
```

## Data Patterns

### Normalized Database
- Reduce redundancy with proper normalization
- Foreign keys for relationships
- Denormalize only for proven read performance needs

### Caching Strategy
- Redis for ephemeral data (sessions, rate limits, queue)
- Database for persistent data
- CDN for static assets
- Cache invalidation on write operations
