# TypeScript Testing Rules

Extends: `../common/testing.md`
Applies to: `**/*.ts`, `**/*.tsx`

## Framework
- **Jest** or **Vitest** for unit/integration tests
- **Playwright** for E2E tests
- Co-locate test files: `component.test.tsx` next to `component.tsx`

## Component Testing
```typescript
import { render, screen, fireEvent } from '@testing-library/react';

test('campaign form submits correctly', async () => {
  render(<CampaignForm />);

  await fireEvent.change(screen.getByLabelText('Name'), {
    target: { value: 'Test Campaign' },
  });
  await fireEvent.click(screen.getByRole('button', { name: 'Create' }));

  expect(screen.getByText('Campaign created')).toBeInTheDocument();
});
```

## API Route Testing
```typescript
import { createMocks } from 'node-mocks-http';

test('POST /api/campaigns returns 201', async () => {
  const { req, res } = createMocks({
    method: 'POST',
    body: { name: 'Test', targetCount: 100 },
  });

  await handler(req, res);

  expect(res._getStatusCode()).toBe(201);
});
```

## Mocking
- Mock API calls with `jest.mock()` or `vi.mock()`
- Mock fetch with `msw` (Mock Service Worker) for integration tests
- Never call real APIs in tests

## What to Test
- User interactions (click, type, submit)
- Component rendering with different props
- Error states and loading states
- API integration (mock the fetch layer)
- NOT: implementation details, internal state, CSS styles
