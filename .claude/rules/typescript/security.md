# TypeScript Security Rules

Extends: `../common/security.md`
Applies to: `**/*.ts`, `**/*.tsx`

## XSS Prevention
```typescript
// NEVER use dangerouslySetInnerHTML with unsanitized data
// If absolutely needed, sanitize with DOMPurify:
import DOMPurify from 'dompurify';
const clean = DOMPurify.sanitize(userInput);
```

## Input Validation
Always validate at API boundaries with Zod:
```typescript
import { z } from 'zod';

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(8),
});

// In API route
const parsed = schema.safeParse(req.body);
if (!parsed.success) {
  return res.status(400).json({ error: parsed.error.issues });
}
```

## Environment Variables
```typescript
// GOOD — validated at startup
const config = z.object({
  DATABASE_URL: z.string().url(),
  API_KEY: z.string().min(1),
}).parse(process.env);

// BAD — unchecked access
const key = process.env.API_KEY; // could be undefined
```

## CORS
```typescript
// GOOD — specific origins
const corsOptions = {
  origin: ['https://nexus-elkana.duckdns.org'],
  methods: ['GET', 'POST', 'PUT', 'DELETE'],
};

// BAD — wildcard in production
const corsOptions = { origin: '*' };
```

## Dependencies
```bash
npm audit          # Check for known vulnerabilities
npm audit fix      # Auto-fix where possible
```
