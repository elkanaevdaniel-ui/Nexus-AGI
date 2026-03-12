# Python Testing Rules

Extends: `../common/testing.md`
Applies to: `**/*.py`

## Framework
- **pytest** with **pytest-asyncio** for async tests
- Location: `tests/` directories alongside source

## Fixtures
```python
import pytest
from httpx import AsyncClient, ASGITransport

@pytest.fixture
async def async_client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest.fixture
async def db_session():
    async with async_session() as session:
        yield session
        await session.rollback()
```

## Test Pattern: Arrange-Act-Assert
```python
@pytest.mark.asyncio
async def test_create_lead(async_client, db_session):
    # Arrange
    lead_data = {"name": "Test Corp", "domain": "test.com"}

    # Act
    response = await async_client.post("/api/leads", json=lead_data)

    # Assert
    assert response.status_code == 201
    assert response.json()["name"] == "Test Corp"
```

## Mocking
- Mock ALL external APIs (Anthropic, OpenAI, Google, Telegram)
- Never call real LLM APIs in tests
- Use `unittest.mock.AsyncMock` for async dependencies
- Mock at the service boundary, not deep internals

## Running Tests
```bash
cd nexus-agi/command-center/orchestrator && pytest
cd nexus-agi/command-center/backend && pytest tests/
```
