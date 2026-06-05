from fastapi import APIRouter, Response, status, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.redis_client import redis_client

router = APIRouter()

SYSTEM_HEALTH = {"status": "ok", "degraded": []}

@router.get("/")
async def healthcheck(response: Response, db: Session = Depends(get_db)) -> dict:
    issues = list(SYSTEM_HEALTH["degraded"])
    
    # 1. Check DB
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
    except Exception as e:
        issues.append(f"database_unreachable: {str(e)}")
        
    # 2. Check Redis
    try:
        await redis_client.client.ping()
    except Exception as e:
        issues.append(f"redis_unreachable: {str(e)}")

    if issues:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "degraded", "issues": issues}
    return {"status": "ok"}

