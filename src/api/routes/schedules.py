"""Schedule management endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.core.models import Schedule, Source, JobExecution, JobStatus

router = APIRouter()


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------


class ScheduleCreate(BaseModel):
    """Schema for creating a schedule."""

    name: str
    description: str | None = None
    cron_expression: str
    timezone: str = "Asia/Seoul"
    task_type: str = "crawl"
    source_ids: list[UUID] | None = None
    keyword_group_ids: list[UUID] | None = None


class ScheduleUpdate(BaseModel):
    """Schema for updating a schedule."""

    name: str | None = None
    description: str | None = None
    cron_expression: str | None = None
    timezone: str | None = None
    is_active: bool | None = None


class ScheduleResponse(BaseModel):
    """Schema for schedule response."""

    id: UUID
    name: str
    description: str | None
    cron_expression: str
    timezone: str
    task_type: str
    is_active: bool
    next_run_at: str | None
    last_run_at: str | None

    class Config:
        from_attributes = True


class JobExecutionResponse(BaseModel):
    """Schema for job execution response."""

    id: UUID
    job_type: str
    status: JobStatus
    started_at: str | None
    finished_at: str | None
    items_collected: int
    items_saved: int
    error_message: str | None

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Schedule Endpoints
# -----------------------------------------------------------------------------


@router.get("")
async def list_schedules(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[ScheduleResponse]:
    """List all schedules."""
    query = select(Schedule)

    if active_only:
        query = query.where(Schedule.is_active == True)

    result = await db.execute(query)
    schedules = result.scalars().all()

    return [ScheduleResponse.model_validate(s) for s in schedules]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule: ScheduleCreate,
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    """Create a new schedule."""
    from croniter import croniter

    # Validate cron expression
    try:
        croniter(schedule.cron_expression)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid cron expression: {str(e)}",
        )

    db_schedule = Schedule(
        name=schedule.name,
        description=schedule.description,
        cron_expression=schedule.cron_expression,
        timezone=schedule.timezone,
        task_type=schedule.task_type,
        keyword_group_ids=[str(id) for id in schedule.keyword_group_ids]
        if schedule.keyword_group_ids
        else None,
    )
    db.add(db_schedule)
    await db.flush()

    # Link sources if provided
    if schedule.source_ids:
        for source_id in schedule.source_ids:
            source = await db.get(Source, source_id)
            if source:
                db_schedule.sources.append(source)

    await db.flush()
    await db.refresh(db_schedule)

    return ScheduleResponse.model_validate(db_schedule)


@router.get("/{schedule_id}")
async def get_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    """Get a specific schedule."""
    schedule = await db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    return ScheduleResponse.model_validate(schedule)


@router.patch("/{schedule_id}")
async def update_schedule(
    schedule_id: UUID,
    schedule_update: ScheduleUpdate,
    db: AsyncSession = Depends(get_db),
) -> ScheduleResponse:
    """Update a schedule."""
    schedule = await db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    update_data = schedule_update.model_dump(exclude_unset=True)

    # Validate cron if being updated
    if "cron_expression" in update_data:
        from croniter import croniter

        try:
            croniter(update_data["cron_expression"])
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid cron expression: {str(e)}",
            )

    for field, value in update_data.items():
        setattr(schedule, field, value)

    await db.flush()
    await db.refresh(schedule)

    return ScheduleResponse.model_validate(schedule)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a schedule."""
    schedule = await db.get(Schedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await db.delete(schedule)


@router.post("/{schedule_id}/run")
async def run_schedule_now(
    schedule_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Manually trigger a schedule to run immediately."""
    result = await db.execute(
        select(Schedule)
        .where(Schedule.id == schedule_id)
        .options(selectinload(Schedule.sources))
    )
    schedule = result.scalar_one_or_none()

    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    from src.scheduler.tasks import crawl_source

    tasks = {}
    for source in schedule.sources:
        task = crawl_source.delay(str(source.id))
        tasks[str(source.id)] = task.id

    return {
        "message": "Schedule triggered",
        "schedule_id": str(schedule_id),
        "tasks_dispatched": len(tasks),
        "task_ids": tasks,
    }


# -----------------------------------------------------------------------------
# Job Execution Endpoints
# -----------------------------------------------------------------------------


@router.get("/{schedule_id}/executions")
async def list_job_executions(
    schedule_id: UUID,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
) -> list[JobExecutionResponse]:
    """List job executions for a schedule."""
    from sqlalchemy import desc

    result = await db.execute(
        select(JobExecution)
        .where(JobExecution.schedule_id == schedule_id)
        .order_by(desc(JobExecution.created_at))
        .limit(limit)
    )
    executions = result.scalars().all()

    return [JobExecutionResponse.model_validate(e) for e in executions]


@router.get("/executions/recent")
async def list_recent_executions(
    limit: int = 50,
    status: JobStatus | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[JobExecutionResponse]:
    """List recent job executions across all schedules."""
    from sqlalchemy import desc

    query = select(JobExecution).order_by(desc(JobExecution.created_at)).limit(limit)

    if status:
        query = query.where(JobExecution.status == status)

    result = await db.execute(query)
    executions = result.scalars().all()

    return [JobExecutionResponse.model_validate(e) for e in executions]
