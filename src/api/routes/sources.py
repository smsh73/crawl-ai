"""Source management endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.models import Source, SourceType, SourceStatus
from src.scheduler.tasks import crawl_source

router = APIRouter()


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------


class SourceCreate(BaseModel):
    """Schema for creating a source."""

    name: str
    url: HttpUrl
    source_type: SourceType
    config: dict[str, Any] | None = None
    crawl_interval_minutes: int = 60


class SourceUpdate(BaseModel):
    """Schema for updating a source."""

    name: str | None = None
    url: HttpUrl | None = None
    config: dict[str, Any] | None = None
    crawl_interval_minutes: int | None = None
    status: SourceStatus | None = None


class SourceResponse(BaseModel):
    """Schema for source response."""

    id: UUID
    name: str
    url: str
    source_type: SourceType
    status: SourceStatus
    config: dict[str, Any] | None
    crawl_interval_minutes: int
    last_crawled_at: str | None
    last_success_at: str | None
    error_count: int

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@router.get("")
async def list_sources(
    source_type: SourceType | None = None,
    status: SourceStatus | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
) -> list[SourceResponse]:
    """List all sources with optional filtering."""
    query = select(Source)

    if source_type:
        query = query.where(Source.source_type == source_type)
    if status:
        query = query.where(Source.status == status)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    sources = result.scalars().all()

    return [SourceResponse.model_validate(s) for s in sources]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_source(
    source: SourceCreate,
    db: AsyncSession = Depends(get_db),
) -> SourceResponse:
    """Create a new source."""
    db_source = Source(
        name=source.name,
        url=str(source.url),
        source_type=source.source_type,
        config=source.config,
        crawl_interval_minutes=source.crawl_interval_minutes,
        status=SourceStatus.ACTIVE,
    )

    db.add(db_source)
    await db.flush()
    await db.refresh(db_source)

    return SourceResponse.model_validate(db_source)


@router.get("/{source_id}")
async def get_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SourceResponse:
    """Get a specific source."""
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    return SourceResponse.model_validate(source)


@router.patch("/{source_id}")
async def update_source(
    source_id: UUID,
    source_update: SourceUpdate,
    db: AsyncSession = Depends(get_db),
) -> SourceResponse:
    """Update a source."""
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    update_data = source_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "url" and value:
            value = str(value)
        setattr(source, field, value)

    await db.flush()
    await db.refresh(source)

    return SourceResponse.model_validate(source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a source."""
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    await db.delete(source)


@router.post("/{source_id}/crawl")
async def trigger_crawl(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Manually trigger a crawl for a source."""
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Dispatch crawl task
    task = crawl_source.delay(str(source_id))

    return {
        "message": "Crawl task dispatched",
        "task_id": task.id,
        "source_id": str(source_id),
    }


@router.post("/{source_id}/analyze")
async def analyze_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Use AI to analyze source and generate/update crawler config."""
    source = await db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Only for web sources
    if source.source_type == SourceType.RSS:
        return {
            "message": "RSS sources don't need config analysis",
            "source_id": str(source_id),
        }

    from src.crawlers.news import WebNewsCrawler
    from src.crawlers.base import CrawlerConfig

    crawler = WebNewsCrawler(str(source_id), source.url)

    try:
        new_config = await crawler.analyze_and_configure()

        # Save AI-generated config
        source.ai_generated_config = vars(new_config)
        source.config_version += 1
        source.config = vars(new_config)

        await db.flush()

        return {
            "message": "Source analyzed successfully",
            "source_id": str(source_id),
            "config": vars(new_config),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze source: {str(e)}",
        )
    finally:
        await crawler.close()
