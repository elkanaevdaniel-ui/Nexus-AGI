# TypeScript Design Patterns

Extends: `../common/patterns.md`
Applies to: `**/*.ts`, `**/*.tsx`, `**/*.js`, `**/*.jsx`

## API Response Format
```typescript
interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  metadata?: Record<string, unknown>;
}
```

## Custom Hooks Pattern
```typescript
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}
```

## Repository Pattern
```typescript
interface Repository<T> {
  findAll(): Promise<T[]>;
  findById(id: string): Promise<T | null>;
  create(data: Omit<T, 'id'>): Promise<T>;
  update(id: string, data: Partial<T>): Promise<T>;
  delete(id: string): Promise<void>;
}
```

## Server Component Data Fetching (Next.js)
```typescript
// page.tsx (server component — default)
export async function CampaignPage({ params }: { params: { id: string } }) {
  const campaign = await getCampaign(params.id);
  return <CampaignView campaign={campaign} />;
}

// campaign-view.tsx (client component — only if interactive)
"use client";
export function CampaignView({ campaign }: { campaign: Campaign }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div onClick={() => setExpanded(!expanded)}>
      {campaign.name}
    </div>
  );
}
```

## Error Boundary
```typescript
"use client";
export function ErrorBoundary({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div>
      <h2>Something went wrong</h2>
      <button onClick={reset}>Try again</button>
    </div>
  );
}
```
