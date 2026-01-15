"""Admin API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from agent_marketplace_api.api.deps import AdminUserDep
from agent_marketplace_api.database import get_db
from agent_marketplace_api.models import Agent, Category, User, agent_categories
from agent_marketplace_api.schemas.user import UserSummary

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
    _admin: AdminUserDep,
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
    _admin: AdminUserDep,
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
    _admin: AdminUserDep,
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

    # Check if category has agents
    if category.agent_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete category with {category.agent_count} agent(s). Move them first.",
        )

    await db.delete(category)
    await db.commit()


# =============================================================================
# Agent Management Endpoints
# =============================================================================


class AdminAgentUpdate(BaseModel):
    """Schema for admin updating an agent."""

    name: str | None = Field(None, min_length=3, max_length=255)
    description: str | None = Field(None, min_length=10)
    category: str | None = Field(None, min_length=1, max_length=100)
    is_public: bool | None = None
    is_validated: bool | None = None


class AdminAgentResponse(BaseModel):
    """Agent response for admin endpoints."""

    id: int
    name: str
    slug: str
    description: str
    author: UserSummary
    current_version: str
    downloads: int = 0
    stars: int = 0
    rating: float = 0.0
    category: str
    is_public: bool = True
    is_validated: bool = False

    class Config:
        from_attributes = True


class AdminAgentListResponse(BaseModel):
    """Response for admin agent list."""

    items: list[AdminAgentResponse]
    total: int


class BulkCategoryUpdate(BaseModel):
    """Schema for bulk moving agents to a category."""

    agent_slugs: list[str] = Field(..., min_length=1)
    new_category: str = Field(..., min_length=1, max_length=100)


class BulkUpdateResponse(BaseModel):
    """Response for bulk update."""

    updated: int


@router.get("/agents", response_model=AdminAgentListResponse)
async def list_agents_admin(
    _admin: AdminUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    category: str | None = None,
) -> AdminAgentListResponse:
    """List all agents for admin. Includes private agents."""
    query = (
        select(Agent)
        .options(selectinload(Agent.author), selectinload(Agent.categories))
        .order_by(Agent.created_at.desc())
    )

    # Filter by category if provided
    if category:
        query = query.join(Agent.categories).where(Category.slug == category)

    # Get total count
    count_query = select(func.count(Agent.id))
    if category:
        count_query = count_query.join(Agent.categories).where(Category.slug == category)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    agents = result.scalars().unique().all()

    # Build response with category info
    items = []
    for agent in agents:
        cat_name = agent.categories[0].slug if agent.categories else "uncategorized"
        items.append(
            AdminAgentResponse(
                id=agent.id,
                name=agent.name,
                slug=agent.slug,
                description=agent.description,
                author=UserSummary(
                    id=agent.author.id,
                    username=agent.author.username,
                    avatar_url=agent.author.avatar_url,
                ),
                current_version=agent.current_version,
                downloads=agent.downloads,
                stars=agent.stars,
                rating=float(agent.rating),
                category=cat_name,
                is_public=agent.is_public,
                is_validated=agent.is_validated,
            )
        )

    return AdminAgentListResponse(items=items, total=total)


@router.put("/agents/{slug}", response_model=AdminAgentResponse)
async def update_agent_admin(
    slug: str,
    data: AdminAgentUpdate,
    _admin: AdminUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminAgentResponse:
    """Update an agent. Admin only."""
    result = await db.execute(
        select(Agent)
        .options(selectinload(Agent.author), selectinload(Agent.categories))
        .where(Agent.slug == slug)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{slug}' not found",
        )

    # Update fields if provided
    if data.name is not None:
        agent.name = data.name
    if data.description is not None:
        agent.description = data.description
    if data.is_public is not None:
        agent.is_public = data.is_public
    if data.is_validated is not None:
        agent.is_validated = data.is_validated

    # Handle category change
    if data.category is not None:
        # Find new category
        cat_result = await db.execute(select(Category).where(Category.slug == data.category))
        new_category = cat_result.scalar_one_or_none()
        if not new_category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category '{data.category}' not found",
            )

        # Get old category for count update
        old_category = agent.categories[0] if agent.categories else None

        # Update category relationship
        await db.execute(delete(agent_categories).where(agent_categories.c.agent_id == agent.id))
        await db.execute(
            insert(agent_categories).values(agent_id=agent.id, category_id=new_category.id)
        )

        # Update category counts
        if old_category and old_category.id != new_category.id:
            old_category.agent_count = max(0, old_category.agent_count - 1)
            new_category.agent_count += 1

    await db.commit()
    await db.refresh(agent)

    # Reload categories
    result = await db.execute(
        select(Agent)
        .options(selectinload(Agent.author), selectinload(Agent.categories))
        .where(Agent.id == agent.id)
    )
    agent = result.scalar_one()

    cat_name = agent.categories[0].slug if agent.categories else "uncategorized"

    return AdminAgentResponse(
        id=agent.id,
        name=agent.name,
        slug=agent.slug,
        description=agent.description,
        author=UserSummary(
            id=agent.author.id,
            username=agent.author.username,
            avatar_url=agent.author.avatar_url,
        ),
        current_version=agent.current_version,
        downloads=agent.downloads,
        stars=agent.stars,
        rating=float(agent.rating),
        category=cat_name,
        is_public=agent.is_public,
        is_validated=agent.is_validated,
    )


@router.delete("/agents/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_admin(
    slug: str,
    _admin: AdminUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete an agent. Admin only."""
    result = await db.execute(
        select(Agent).options(selectinload(Agent.categories)).where(Agent.slug == slug)
    )
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{slug}' not found",
        )

    # Update category count
    if agent.categories:
        for cat in agent.categories:
            cat.agent_count = max(0, cat.agent_count - 1)

    await db.delete(agent)
    await db.commit()


@router.post("/agents/bulk-category", response_model=BulkUpdateResponse)
async def bulk_update_category(
    data: BulkCategoryUpdate,
    _admin: AdminUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BulkUpdateResponse:
    """Bulk move agents to a new category. Admin only."""
    # Find the target category
    cat_result = await db.execute(select(Category).where(Category.slug == data.new_category))
    new_category = cat_result.scalar_one_or_none()
    if not new_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category '{data.new_category}' not found",
        )

    # Find all agents
    result = await db.execute(
        select(Agent)
        .options(selectinload(Agent.categories))
        .where(Agent.slug.in_(data.agent_slugs))
    )
    agents = result.scalars().unique().all()

    updated = 0
    for agent in agents:
        old_category = agent.categories[0] if agent.categories else None

        # Skip if already in target category
        if old_category and old_category.id == new_category.id:
            continue

        # Update category relationship
        await db.execute(delete(agent_categories).where(agent_categories.c.agent_id == agent.id))
        await db.execute(
            insert(agent_categories).values(agent_id=agent.id, category_id=new_category.id)
        )

        # Update counts
        if old_category:
            old_category.agent_count = max(0, old_category.agent_count - 1)
        new_category.agent_count += 1
        updated += 1

    await db.commit()

    return BulkUpdateResponse(updated=updated)


# =============================================================================
# User Management Endpoints
# =============================================================================


class AdminUserResponse(BaseModel):
    """User response for admin endpoints."""

    id: int
    github_id: int
    username: str
    email: str
    avatar_url: str | None = None
    bio: str | None = None
    reputation: int = 0
    role: str = "user"
    is_active: bool = True
    is_blocked: bool = False
    blocked_reason: str | None = None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class AdminUserListResponse(BaseModel):
    """Response for admin user list."""

    items: list[AdminUserResponse]
    total: int


class AdminUserUpdate(BaseModel):
    """Schema for admin updating a user."""

    role: str | None = Field(None, pattern=r"^(user|admin)$")
    bio: str | None = None
    is_active: bool | None = None


class AdminUserBlock(BaseModel):
    """Schema for blocking a user."""

    blocked_reason: str = Field(..., min_length=10, max_length=500)


@router.get("/users", response_model=AdminUserListResponse)
async def list_users_admin(
    _admin: AdminUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: str | None = None,
) -> AdminUserListResponse:
    """List all users for admin."""
    query = select(User).order_by(User.created_at.desc())

    # Search by username or email
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (User.username.ilike(search_pattern)) | (User.email.ilike(search_pattern))
        )

    # Get total count
    count_query = select(func.count(User.id))
    if search:
        search_pattern = f"%{search}%"
        count_query = count_query.where(
            (User.username.ilike(search_pattern)) | (User.email.ilike(search_pattern))
        )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    users = result.scalars().all()

    items = [
        AdminUserResponse(
            id=user.id,
            github_id=user.github_id,
            username=user.username,
            email=user.email,
            avatar_url=user.avatar_url,
            bio=user.bio,
            reputation=user.reputation,
            role=user.role,
            is_active=user.is_active,
            is_blocked=user.is_blocked,
            blocked_reason=user.blocked_reason,
            created_at=user.created_at.isoformat(),
            updated_at=user.updated_at.isoformat(),
        )
        for user in users
    ]

    return AdminUserListResponse(items=items, total=total)


@router.get("/users/{user_id}", response_model=AdminUserResponse)
async def get_user_admin(
    user_id: int,
    _admin: AdminUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserResponse:
    """Get a user by ID. Admin only."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    return AdminUserResponse(
        id=user.id,
        github_id=user.github_id,
        username=user.username,
        email=user.email,
        avatar_url=user.avatar_url,
        bio=user.bio,
        reputation=user.reputation,
        role=user.role,
        is_active=user.is_active,
        is_blocked=user.is_blocked,
        blocked_reason=user.blocked_reason,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
    )


@router.put("/users/{user_id}", response_model=AdminUserResponse)
async def update_user_admin(
    user_id: int,
    data: AdminUserUpdate,
    _admin: AdminUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserResponse:
    """Update a user. Admin only."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    # Update fields if provided
    if data.role is not None:
        user.role = data.role
    if data.bio is not None:
        user.bio = data.bio
    if data.is_active is not None:
        user.is_active = data.is_active

    await db.commit()
    await db.refresh(user)

    return AdminUserResponse(
        id=user.id,
        github_id=user.github_id,
        username=user.username,
        email=user.email,
        avatar_url=user.avatar_url,
        bio=user.bio,
        reputation=user.reputation,
        role=user.role,
        is_active=user.is_active,
        is_blocked=user.is_blocked,
        blocked_reason=user.blocked_reason,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
    )


@router.post("/users/{user_id}/block", response_model=AdminUserResponse)
async def block_user_admin(
    user_id: int,
    data: AdminUserBlock,
    _admin: AdminUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserResponse:
    """Block a user. Admin only."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    if user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot block an admin user",
        )

    user.is_blocked = True
    user.blocked_reason = data.blocked_reason

    await db.commit()
    await db.refresh(user)

    return AdminUserResponse(
        id=user.id,
        github_id=user.github_id,
        username=user.username,
        email=user.email,
        avatar_url=user.avatar_url,
        bio=user.bio,
        reputation=user.reputation,
        role=user.role,
        is_active=user.is_active,
        is_blocked=user.is_blocked,
        blocked_reason=user.blocked_reason,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
    )


@router.post("/users/{user_id}/unblock", response_model=AdminUserResponse)
async def unblock_user_admin(
    user_id: int,
    _admin: AdminUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AdminUserResponse:
    """Unblock a user. Admin only."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    user.is_blocked = False
    user.blocked_reason = None

    await db.commit()
    await db.refresh(user)

    return AdminUserResponse(
        id=user.id,
        github_id=user.github_id,
        username=user.username,
        email=user.email,
        avatar_url=user.avatar_url,
        bio=user.bio,
        reputation=user.reputation,
        role=user.role,
        is_active=user.is_active,
        is_blocked=user.is_blocked,
        blocked_reason=user.blocked_reason,
        created_at=user.created_at.isoformat(),
        updated_at=user.updated_at.isoformat(),
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_admin(
    user_id: int,
    _admin: AdminUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete a user. Admin only."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    if user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete an admin user",
        )

    await db.delete(user)
    await db.commit()
