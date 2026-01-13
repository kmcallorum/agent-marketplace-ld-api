"""Categories API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.database import get_db
from agent_marketplace_api.models import Agent, Category
from agent_marketplace_api.schemas import AgentListResponse, AgentSummary

router = APIRouter()


class CategoryResponse(BaseModel):
    """Category response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    icon: str | None = None
    description: str | None = None
    agent_count: int = 0


class CategoriesResponse(BaseModel):
    """List of categories response."""

    categories: list[CategoryResponse]


@router.get("", response_model=CategoriesResponse)
async def get_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CategoriesResponse:
    """Get all categories."""
    result = await db.execute(select(Category).order_by(Category.name))
    categories = result.scalars().all()

    return CategoriesResponse(
        categories=[CategoryResponse.model_validate(c) for c in categories]
    )


@router.get("/{slug}", response_model=CategoryResponse)
async def get_category(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryResponse:
    """Get category by slug."""
    result = await db.execute(select(Category).where(Category.slug == slug))
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{slug}' not found",
        )

    return CategoryResponse.model_validate(category)


@router.get("/{slug}/agents", response_model=AgentListResponse)
async def get_category_agents(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AgentListResponse:
    """Get agents in a category."""
    result = await db.execute(select(Category).where(Category.slug == slug))
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{slug}' not found",
        )

    # Get agents with this category
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Agent)
        .join(Agent.categories)
        .where(Category.id == category.id)
        .options(selectinload(Agent.author))
        .order_by(Agent.downloads.desc())
        .limit(limit)
        .offset(offset)
    )
    agents = result.scalars().all()

    # Get total count
    from sqlalchemy import func

    count_result = await db.execute(
        select(func.count(Agent.id))
        .join(Agent.categories)
        .where(Category.id == category.id)
    )
    total = count_result.scalar() or 0

    return AgentListResponse(
        items=[AgentSummary.model_validate(a) for a in agents],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(agents) < total,
    )
