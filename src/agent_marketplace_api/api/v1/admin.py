"""Admin API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.api.deps import AdminUserDep
from agent_marketplace_api.database import get_db
from agent_marketplace_api.models import Category

router = APIRouter()


class CategoryCreate(BaseModel):
    """Schema for creating a category."""

    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    icon: str | None = Field(None, max_length=50)
    description: str | None = None


class CategoryUpdate(BaseModel):
    """Schema for updating a category."""

    name: str | None = Field(None, min_length=1, max_length=100)
    icon: str | None = None
    description: str | None = None


class CategoryResponse(BaseModel):
    """Category response schema."""

    id: int
    name: str
    slug: str
    icon: str | None = None
    description: str | None = None
    agent_count: int = 0

    class Config:
        from_attributes = True


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate,
    admin: AdminUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryResponse:
    """Create a new category. Admin only."""
    # Check for duplicate slug
    result = await db.execute(select(Category).where(Category.slug == data.slug))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category with slug '{data.slug}' already exists",
        )

    # Check for duplicate name
    result = await db.execute(select(Category).where(Category.name == data.name))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category with name '{data.name}' already exists",
        )

    category = Category(
        name=data.name,
        slug=data.slug,
        icon=data.icon,
        description=data.description,
        agent_count=0,
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)

    return CategoryResponse.model_validate(category)


@router.put("/categories/{slug}", response_model=CategoryResponse)
async def update_category(
    slug: str,
    data: CategoryUpdate,
    admin: AdminUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CategoryResponse:
    """Update a category. Admin only."""
    result = await db.execute(select(Category).where(Category.slug == slug))
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{slug}' not found",
        )

    # Check for name conflict if updating name
    if data.name and data.name != category.name:
        result = await db.execute(select(Category).where(Category.name == data.name))
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category with name '{data.name}' already exists",
            )
        category.name = data.name

    if data.icon is not None:
        category.icon = data.icon
    if data.description is not None:
        category.description = data.description

    await db.commit()
    await db.refresh(category)

    return CategoryResponse.model_validate(category)


@router.delete("/categories/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    slug: str,
    admin: AdminUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a category. Admin only."""
    result = await db.execute(select(Category).where(Category.slug == slug))
    category = result.scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{slug}' not found",
        )

    await db.delete(category)
    await db.commit()
