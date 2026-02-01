"""Keyword management endpoints."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.core.models import Keyword, KeywordGroup

router = APIRouter()


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------


class KeywordCreate(BaseModel):
    """Schema for creating a keyword."""

    keyword: str
    synonyms: list[str] | None = None
    weight: float = 1.0


class KeywordGroupCreate(BaseModel):
    """Schema for creating a keyword group."""

    name: str
    description: str | None = None
    keywords: list[KeywordCreate] | None = None


class KeywordGroupUpdate(BaseModel):
    """Schema for updating a keyword group."""

    name: str | None = None
    description: str | None = None
    is_active: bool | None = None


class KeywordResponse(BaseModel):
    """Schema for keyword response."""

    id: UUID
    keyword: str
    synonyms: list[str] | None
    weight: float
    is_active: bool

    class Config:
        from_attributes = True


class KeywordGroupResponse(BaseModel):
    """Schema for keyword group response."""

    id: UUID
    name: str
    description: str | None
    is_active: bool
    keywords: list[KeywordResponse]

    class Config:
        from_attributes = True


# -----------------------------------------------------------------------------
# Keyword Group Endpoints
# -----------------------------------------------------------------------------


@router.get("/groups")
async def list_keyword_groups(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[KeywordGroupResponse]:
    """List all keyword groups."""
    query = select(KeywordGroup).options(selectinload(KeywordGroup.keywords))

    if active_only:
        query = query.where(KeywordGroup.is_active == True)

    result = await db.execute(query)
    groups = result.scalars().all()

    return [KeywordGroupResponse.model_validate(g) for g in groups]


@router.post("/groups", status_code=status.HTTP_201_CREATED)
async def create_keyword_group(
    group: KeywordGroupCreate,
    db: AsyncSession = Depends(get_db),
) -> KeywordGroupResponse:
    """Create a new keyword group with optional keywords."""
    # Check for duplicate name
    existing = await db.execute(
        select(KeywordGroup).where(KeywordGroup.name == group.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Keyword group '{group.name}' already exists",
        )

    db_group = KeywordGroup(
        name=group.name,
        description=group.description,
    )
    db.add(db_group)
    await db.flush()

    # Add keywords if provided
    if group.keywords:
        for kw in group.keywords:
            db_keyword = Keyword(
                group_id=db_group.id,
                keyword=kw.keyword,
                synonyms=kw.synonyms,
                weight=kw.weight,
            )
            db.add(db_keyword)

    await db.flush()
    await db.refresh(db_group)

    # Reload with keywords
    result = await db.execute(
        select(KeywordGroup)
        .where(KeywordGroup.id == db_group.id)
        .options(selectinload(KeywordGroup.keywords))
    )
    db_group = result.scalar_one()

    return KeywordGroupResponse.model_validate(db_group)


@router.get("/groups/{group_id}")
async def get_keyword_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> KeywordGroupResponse:
    """Get a specific keyword group."""
    result = await db.execute(
        select(KeywordGroup)
        .where(KeywordGroup.id == group_id)
        .options(selectinload(KeywordGroup.keywords))
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Keyword group not found")

    return KeywordGroupResponse.model_validate(group)


@router.patch("/groups/{group_id}")
async def update_keyword_group(
    group_id: UUID,
    group_update: KeywordGroupUpdate,
    db: AsyncSession = Depends(get_db),
) -> KeywordGroupResponse:
    """Update a keyword group."""
    result = await db.execute(
        select(KeywordGroup)
        .where(KeywordGroup.id == group_id)
        .options(selectinload(KeywordGroup.keywords))
    )
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Keyword group not found")

    update_data = group_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(group, field, value)

    await db.flush()
    await db.refresh(group)

    return KeywordGroupResponse.model_validate(group)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a keyword group and all its keywords."""
    group = await db.get(KeywordGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Keyword group not found")

    await db.delete(group)


# -----------------------------------------------------------------------------
# Keyword Endpoints
# -----------------------------------------------------------------------------


@router.post("/groups/{group_id}/keywords", status_code=status.HTTP_201_CREATED)
async def add_keyword(
    group_id: UUID,
    keyword: KeywordCreate,
    db: AsyncSession = Depends(get_db),
) -> KeywordResponse:
    """Add a keyword to a group."""
    group = await db.get(KeywordGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Keyword group not found")

    db_keyword = Keyword(
        group_id=group_id,
        keyword=keyword.keyword,
        synonyms=keyword.synonyms,
        weight=keyword.weight,
    )
    db.add(db_keyword)
    await db.flush()
    await db.refresh(db_keyword)

    return KeywordResponse.model_validate(db_keyword)


@router.delete("/keywords/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_keyword(
    keyword_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a keyword."""
    keyword = await db.get(Keyword, keyword_id)
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")

    await db.delete(keyword)


@router.patch("/keywords/{keyword_id}")
async def update_keyword(
    keyword_id: UUID,
    keyword_update: KeywordCreate,
    db: AsyncSession = Depends(get_db),
) -> KeywordResponse:
    """Update a keyword."""
    keyword = await db.get(Keyword, keyword_id)
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")

    keyword.keyword = keyword_update.keyword
    keyword.synonyms = keyword_update.synonyms
    keyword.weight = keyword_update.weight

    await db.flush()
    await db.refresh(keyword)

    return KeywordResponse.model_validate(keyword)
