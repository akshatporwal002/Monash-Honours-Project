from functools import lru_cache

from fastapi import APIRouter, Depends, Response

from app.core.config import settings
from app.core.readiness import ReadinessProbe, worker_health
from app.db.session import engine
from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


@lru_cache
def get_readiness_probe() -> ReadinessProbe:
    return ReadinessProbe(engine, settings, worker_health)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
async def readiness_check(
    response: Response,
    probe: ReadinessProbe = Depends(get_readiness_probe),
) -> ReadinessResponse:
    result = probe.check()
    if result.status == "not_ready":
        response.status_code = 503
    response.headers["Cache-Control"] = "no-store"
    return result
