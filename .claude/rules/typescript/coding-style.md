# TypeScript Coding Style

Extends: `../common/coding-style.md`
Applies to: `**/*.ts`, `**/*.tsx`, `**/*.js`, `**/*.jsx`

## Standards
- TypeScript strict mode — no `any` types
- 2-space indentation
- Named exports only — no default exports
- Prefer `interface` over `type` for objects

## Immutability
```typescript
// GOOD — spread operator
const updated = { ...user, name: newName };

// BAD — mutation
user.name = newName;
```

## Error Handling
```typescript
// GOOD — async/await with try-catch
async function fetchLeads(): Promise<Lead[]> {
  try {
    const response = await fetch('/api/leads');
    return await response.json();
  } catch (error) {
    logger.error('Failed to fetch leads', { error });
    throw new Error('Failed to fetch leads');
  }
}
```

## Input Validation (Zod)
```typescript
import { z } from 'zod';

const CampaignSchema = z.object({
  name: z.string().min(1).max(100),
  targetCount: z.number().int().min(1).max(10000),
  icpDescription: z.string().min(10),
});
```

## Console.log
- NEVER use `console.log` in production code
- Use proper logging library instead
- Automated hooks detect and warn about console.log

## Next.js Specific
- Server components by default
- `"use client"` only when needed (onClick, useState, useEffect)
- Named exports for all components
- Fetch data in server components, pass as props
