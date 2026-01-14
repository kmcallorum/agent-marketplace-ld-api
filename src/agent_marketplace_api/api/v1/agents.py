"""Agent API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.api.deps import AgentServiceDep, CurrentUserDep
from agent_marketplace_api.database import get_db
from agent_marketplace_api.models import Agent, agent_stars
from agent_marketplace_api.schemas import AgentCreate, AgentListResponse, AgentResponse
from agent_marketplace_api.schemas.agent import AgentSummary
from agent_marketplace_api.services.agent_service import AgentNotFoundError
from agent_marketplace_api.storage import StorageService, UploadError, get_storage_service

router = APIRouter()


def get_storage() -> StorageService:
    """Get storage service dependency."""
    return get_storage_service()


StorageDep = Annotated[StorageService, Depends(get_storage)]


class AgentCreateResponse(BaseModel):
    """Response for agent creation (202 Accepted)."""

    id: int
    slug: str
    validation_status: str = "pending"
    message: str = "Agent submitted for validation"


@router.get("", response_model=AgentListResponse)
async def list_agents(
    service: AgentServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    category: str | None = None,
    sort: Annotated[str, Query()] = "created_at",
) -> AgentListResponse:
    """List public agents with optional filtering and pagination."""
    result = await service.list_agents(
        limit=limit,
        offset=offset,
        category=category,
        sort_by=sort,
    )

    return AgentListResponse(
        items=[
            AgentSummary(
                id=agent.id,
                name=agent.name,
                slug=agent.slug,
                description=agent.description,
                author=agent.author,
                current_version=agent.current_version,
                downloads=agent.downloads,
                stars=agent.stars,
                rating=agent.rating,
                is_validated=agent.is_validated,
                created_at=agent.created_at,
            )
            for agent in result.items
        ],
        total=result.total,
        limit=result.limit,
        offset=result.offset,
        has_more=result.has_more,
    )


@router.get("/{slug}", response_model=AgentResponse)
async def get_agent(
    slug: str,
    service: AgentServiceDep,
) -> AgentResponse:
    """Get agent details by slug."""
    try:
        agent = await service.get_agent(slug)
    except AgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    return AgentResponse(
        id=agent.id,
        name=agent.name,
        slug=agent.slug,
        description=agent.description,
        author=agent.author,
        current_version=agent.current_version,
        downloads=agent.downloads,
        stars=agent.stars,
        rating=agent.rating,
        is_public=agent.is_public,
        is_validated=agent.is_validated,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
        versions=agent.versions,
    )


@router.post("", response_model=AgentCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_agent(
    current_user: CurrentUserDep,
    service: AgentServiceDep,
    storage: StorageDep,
    name: Annotated[str, Form(min_length=3, max_length=255)],
    description: Annotated[str, Form(min_length=10)],
    category: Annotated[str, Form(min_length=1, max_length=100)],
    version: Annotated[str, Form(pattern=r"^\d+\.\d+\.\d+$")],
    code: Annotated[UploadFile, File()],
) -> AgentCreateResponse:
    """Create a new agent with file upload (requires authentication).

    Accepts multipart/form-data with agent metadata and code file.
    The code file should be a ZIP archive containing the agent implementation.
    """
    # Validate file type
    if code.content_type not in ("application/zip", "application/x-zip-compressed"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code file must be a ZIP archive",
        )

    # Read file content
    file_content = await code.read()

    # Validate file size (max 50MB)
    max_size = 50 * 1024 * 1024  # 50MB
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed ({max_size // (1024 * 1024)}MB)",
        )

    # Generate storage key
    storage_key = f"agents/{current_user.username}/{name}-{version}.zip"

    # Upload to S3/MinIO
    try:
        await storage.upload_file(
            key=storage_key,
            file_data=file_content,
            content_type="application/zip",
        )
    except UploadError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {e}",
        ) from e

    # Create agent in database
    data = AgentCreate(
        name=name,
        description=description,
        category=category,
        version=version,
    )

    agent = await service.create_agent(
        data=data,
        author=current_user,
        storage_key=storage_key,
    )

    return AgentCreateResponse(
        id=agent.id,
        slug=agent.slug,
    )


@router.post("/{slug}/star", status_code=status.HTTP_204_NO_CONTENT)
async def star_agent(
    slug: str,
    current_user: CurrentUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Star an agent (requires authentication)."""
    # Find the agent
    result = await db.execute(select(Agent).where(Agent.slug == slug))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{slug}' not found",
        )

    # Check if already starred
    check = await db.execute(
        select(agent_stars).where(
            agent_stars.c.user_id == current_user.id,
            agent_stars.c.agent_id == agent.id,
        )
    )
    if check.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent already starred",
        )

    # Add star
    await db.execute(
        agent_stars.insert().values(user_id=current_user.id, agent_id=agent.id)
    )
    agent.stars += 1
    await db.commit()


@router.delete("/{slug}/star", status_code=status.HTTP_204_NO_CONTENT)
async def unstar_agent(
    slug: str,
    current_user: CurrentUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Unstar an agent (requires authentication)."""
    # Find the agent
    result = await db.execute(select(Agent).where(Agent.slug == slug))
    agent = result.scalar_one_or_none()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{slug}' not found",
        )

    # Check if starred
    check = await db.execute(
        select(agent_stars).where(
            agent_stars.c.user_id == current_user.id,
            agent_stars.c.agent_id == agent.id,
        )
    )
    if not check.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent not starred",
        )

    # Remove star
    await db.execute(
        agent_stars.delete().where(
            agent_stars.c.user_id == current_user.id,
            agent_stars.c.agent_id == agent.id,
        )
    )
    agent.stars = max(0, agent.stars - 1)
    await db.commit()
