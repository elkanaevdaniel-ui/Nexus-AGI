# Python Design Patterns

Extends: `../common/patterns.md`
Applies to: `**/*.py`, `**/*.pyi`

## Protocol (Duck Typing)
Use `typing.Protocol` for structural types without inheritance:
```python
from typing import Protocol

class Searchable(Protocol):
    def search(self, query: str) -> list[dict]: ...
```

## Dataclasses as DTOs
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class LeadScore:
    lead_id: str
    score: float
    factors: list[str]
```

## Context Managers
Use `with` for resource lifecycle:
```python
async with async_session() as session:
    result = await session.execute(query)
```

## FastAPI Service Pattern
```python
# routes.py — thin route
@router.post("/leads", response_model=LeadResponse)
async def create_lead(
    data: LeadCreate,
    session: AsyncSession = Depends(get_session),
):
    return await lead_service.create(session, data)

# service.py — business logic
async def create(session: AsyncSession, data: LeadCreate) -> Lead:
    lead = Lead(**data.model_dump())
    session.add(lead)
    await session.commit()
    return lead
```

## LangGraph Node Pattern
```python
async def score_lead(state: PipelineState) -> PipelineState:
    """Single-responsibility node in the LangGraph pipeline."""
    score = await llm_chain.ainvoke(state["lead_data"])
    return {**state, "score": score}
```

## Error Handling
```python
from fastapi import HTTPException

async def get_lead(lead_id: str, session: AsyncSession) -> Lead:
    lead = await session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    return lead
```
