from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.health_checks import get_readiness_report

router = APIRouter()


@router.get("/")
def healthcheck() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "version": settings.version,
        "environment": settings.environment,
    }


@router.get("/ready")
async def readiness_check():
    payload, status_code = await get_readiness_report()
    return JSONResponse(status_code=status_code, content=payload)
