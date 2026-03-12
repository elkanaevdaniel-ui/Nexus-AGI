"""Lead Gen Service — FastAPI application."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel

from src.config import settings
from src.database import init_db


class HealthResponse(BaseModel):
    status: str
    service: str


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize database on startup and recover stuck pipelines."""
    init_db()
    _recover_stuck_pipelines()
    yield


def _recover_stuck_pipelines() -> None:
    """Reset campaigns stuck in mid-pipeline stages (e.g. after a crash/restart)."""
    from src.database import SessionLocal
    from src.models.lead import Campaign

    stuck_stages = ("searching", "scoring", "enriching", "drafting")
    db = SessionLocal()
    try:
        stuck = (
            db.query(Campaign)
            .filter(Campaign.pipeline_stage.in_(stuck_stages))
            .all()
        )
        for campaign in stuck:
            campaign.pipeline_stage = "failed"
        if stuck:
            db.commit()
            import logging
            logging.getLogger(__name__).warning(
                "Recovered %d stuck campaigns on startup: %s",
                len(stuck),
                [c.id for c in stuck],
            )
    finally:
        db.close()


app = FastAPI(
    title="NEXUS Lead Gen",
    description="AI-powered B2B SaaS lead generation with Apollo.io integration",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)

# Register routers
from src.api.campaigns import router as campaigns_router
from src.api.deals import router as deals_router
from src.api.leads import router as leads_router
from src.api.outreach import router as outreach_router

app.include_router(campaigns_router)
app.include_router(leads_router)
app.include_router(outreach_router)
app.include_router(deals_router)


@app.get("/health")
@app.get("/api/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="lead-gen")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.lead_gen_port,
        reload=True,
    )
