"""Health check endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "app": settings.app_name,
        "env": settings.app_env,
    }


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness check with database connectivity."""
    try:
        # Check database
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Check AI providers
    ai_providers = settings.available_ai_providers

    return {
        "status": "ready" if db_status == "connected" else "not_ready",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": db_status,
            "ai_providers": ai_providers,
        },
    }
