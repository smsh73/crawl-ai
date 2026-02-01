"""Content management endpoints."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.models import Content, ContentStatus

router = APIRouter()


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------


class ContentResponse(BaseModel):
    """Schema for content response."""

    id: UUID
    url: str
    title: str
    content: str | None
    summary: str | None
    categories: list[str] | None
    entities: dict[str, Any] | None
    sentiment: str | None
    relevance_score: float | None
    importance_score: float | None
    matched_keywords: list[str] | None
    status: ContentStatus
    published_at: datetime | None
    collected_at: datetime
    processed_at: datetime | None

    class Config:
        from_attributes = True


class ContentListResponse(BaseModel):
    """Schema for paginated content list."""

    items: list[ContentResponse]
    total: int
    page: int
    page_size: int


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@router.get("")
async def list_contents(
    status: ContentStatus | None = None,
    keyword: str | None = Query(None, description="Filter by matched keyword"),
    category: str | None = Query(None, description="Filter by category"),
    min_importance: float | None = Query(None, ge=0, le=1),
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ContentListResponse:
    """List contents with filtering and pagination."""
    query = select(Content)

    # Apply filters
    if status:
        query = query.where(Content.status == status)

    if keyword:
        query = query.where(Content.matched_keywords.contains([keyword]))

    if category:
        query = query.where(Content.categories.contains([category]))

    if min_importance is not None:
        query = query.where(Content.importance_score >= min_importance)

    if start_date:
        query = query.where(Content.collected_at >= start_date)

    if end_date:
        query = query.where(Content.collected_at <= end_date)

    # Get total count
    from sqlalchemy import func

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = (
        query.order_by(desc(Content.importance_score), desc(Content.collected_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    contents = result.scalars().all()

    return ContentListResponse(
        items=[ContentResponse.model_validate(c) for c in contents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/search")
async def search_contents(
    q: str = Query(..., min_length=2, description="Search query"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> ContentListResponse:
    """Full-text search contents."""
    # Simple ILIKE search - for production, use PostgreSQL full-text search
    search_pattern = f"%{q}%"

    query = select(Content).where(
        (Content.title.ilike(search_pattern))
        | (Content.content.ilike(search_pattern))
        | (Content.summary.ilike(search_pattern))
    )

    # Get total count
    from sqlalchemy import func

    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    query = (
        query.order_by(desc(Content.importance_score))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    contents = result.scalars().all()

    return ContentListResponse(
        items=[ContentResponse.model_validate(c) for c in contents],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats")
async def get_content_stats(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get content statistics."""
    from datetime import timedelta
    from sqlalchemy import func

    start_date = datetime.utcnow() - timedelta(days=days)

    # Total counts by status
    status_counts = {}
    for status in ContentStatus:
        count_result = await db.execute(
            select(func.count())
            .select_from(Content)
            .where(
                Content.status == status,
                Content.collected_at >= start_date,
            )
        )
        status_counts[status.value] = count_result.scalar() or 0

    # Top keywords
    keyword_result = await db.execute(
        select(func.unnest(Content.matched_keywords), func.count())
        .where(Content.collected_at >= start_date)
        .group_by(func.unnest(Content.matched_keywords))
        .order_by(desc(func.count()))
        .limit(10)
    )
    top_keywords = [{"keyword": kw, "count": count} for kw, count in keyword_result.all()]

    # Top categories
    category_result = await db.execute(
        select(func.unnest(Content.categories), func.count())
        .where(Content.collected_at >= start_date)
        .group_by(func.unnest(Content.categories))
        .order_by(desc(func.count()))
        .limit(10)
    )
    top_categories = [{"category": cat, "count": count} for cat, count in category_result.all()]

    # Daily counts
    daily_result = await db.execute(
        select(
            func.date(Content.collected_at),
            func.count(),
        )
        .where(Content.collected_at >= start_date)
        .group_by(func.date(Content.collected_at))
        .order_by(func.date(Content.collected_at))
    )
    daily_counts = [
        {"date": date.isoformat(), "count": count} for date, count in daily_result.all()
    ]

    return {
        "period_days": days,
        "status_counts": status_counts,
        "top_keywords": top_keywords,
        "top_categories": top_categories,
        "daily_counts": daily_counts,
    }


@router.get("/{content_id}")
async def get_content(
    content_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> ContentResponse:
    """Get a specific content item."""
    content = await db.get(Content, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    return ContentResponse.model_validate(content)


@router.delete("/{content_id}", status_code=204)
async def delete_content(
    content_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a content item."""
    content = await db.get(Content, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    await db.delete(content)


@router.post("/{content_id}/reprocess")
async def reprocess_content(
    content_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Reprocess content through AI pipeline."""
    content = await db.get(Content, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    from src.scheduler.tasks import process_content

    task = process_content.delay(str(content_id))

    return {
        "message": "Reprocessing task dispatched",
        "task_id": task.id,
        "content_id": str(content_id),
    }
