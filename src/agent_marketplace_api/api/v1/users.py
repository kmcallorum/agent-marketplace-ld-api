"""User profile API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.database import get_db
from agent_marketplace_api.repositories.agent_repo import AgentRepository
from agent_marketplace_api.repositories.user_repo import UserRepository
from agent_marketplace_api.schemas import AgentListResponse, AgentSummary, UserResponse

router = APIRouter()


class UserProfileResponse(UserResponse):
    """User profile with stats."""

    stats: "UserStats | None" = None


class UserStats(BaseModel):
    """User statistics."""

    agents_published: int = 0
    total_downloads: int = 0
    total_stars: int = 0


UserProfileResponse.model_rebuild()


@router.get("/{username}", response_model=UserProfileResponse)
async def get_user_profile(
    username: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserProfileResponse:
    """Get user profile by username."""
    user_repo = UserRepository(db)
    user = await user_repo.find_by_username(username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found",
        )

    # Get user's agents to calculate stats
    agent_repo = AgentRepository(db)
    agents = await agent_repo.find_by_author(user.id, limit=1000)

    stats = UserStats(
        agents_published=len(agents),
        total_downloads=sum(a.downloads for a in agents),
        total_stars=sum(a.stars for a in agents),
    )

    return UserProfileResponse(
        **UserResponse.model_validate(user).model_dump(),
        stats=stats,
    )


@router.get("/{username}/agents", response_model=AgentListResponse)
async def get_user_agents(
    username: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AgentListResponse:
    """Get agents published by a user."""
    user_repo = UserRepository(db)
    user = await user_repo.find_by_username(username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found",
        )

    agent_repo = AgentRepository(db)
    agents = await agent_repo.find_by_author(user.id, limit=limit, offset=offset)

    # Get total count
    all_agents = await agent_repo.find_by_author(user.id, limit=10000)
    total = len(all_agents)

    return AgentListResponse(
        items=[AgentSummary.model_validate(a) for a in agents],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(agents) < total,
    )


@router.get("/{username}/starred", response_model=AgentListResponse)
async def get_user_starred_agents(
    username: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AgentListResponse:
    """Get agents starred by a user."""
    from sqlalchemy import func, select
    from sqlalchemy.orm import selectinload

    from agent_marketplace_api.models import Agent
    from agent_marketplace_api.models.user import agent_stars

    user_repo = UserRepository(db)
    user = await user_repo.find_by_username(username)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{username}' not found",
        )

    # Get starred agents with pagination
    result = await db.execute(
        select(Agent)
        .join(agent_stars, agent_stars.c.agent_id == Agent.id)
        .where(agent_stars.c.user_id == user.id)
        .options(selectinload(Agent.author))
        .order_by(agent_stars.c.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    agents = result.scalars().all()

    # Get total count
    count_result = await db.execute(
        select(func.count())
        .select_from(agent_stars)
        .where(agent_stars.c.user_id == user.id)
    )
    total = count_result.scalar() or 0

    return AgentListResponse(
        items=[AgentSummary.model_validate(a) for a in agents],
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(agents) < total,
    )
