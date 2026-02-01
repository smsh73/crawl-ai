"""Report generation endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.processors.report_generator import ReportGenerator

router = APIRouter()


@router.get("/daily")
async def get_daily_report(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Generate and return daily intelligence report."""
    generator = ReportGenerator()
    report = await generator.generate_daily()
    return report


@router.get("/weekly")
async def get_weekly_report(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Generate and return weekly intelligence report."""
    generator = ReportGenerator()
    report = await generator.generate_weekly()
    return report


@router.get("/custom")
async def get_custom_report(
    topic: str = Query(..., min_length=2, description="Report topic"),
    days: int = Query(30, ge=1, le=90, description="Number of days to analyze"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Generate custom report for a specific topic."""
    generator = ReportGenerator()
    report = await generator.generate_custom(topic=topic, days=days)
    return report


@router.post("/generate/daily")
async def trigger_daily_report(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Trigger daily report generation task."""
    from src.scheduler.tasks import generate_daily_report

    task = generate_daily_report.delay()

    return {
        "message": "Daily report generation task dispatched",
        "task_id": task.id,
    }


@router.post("/generate/weekly")
async def trigger_weekly_report(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Trigger weekly report generation task."""
    from src.scheduler.tasks import generate_weekly_report

    task = generate_weekly_report.delay()

    return {
        "message": "Weekly report generation task dispatched",
        "task_id": task.id,
    }
