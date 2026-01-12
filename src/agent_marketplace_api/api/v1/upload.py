"""File upload and download endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse

from agent_marketplace_api.api.deps import AgentServiceDep, CurrentUserDep
from agent_marketplace_api.services.agent_service import AgentNotFoundError
from agent_marketplace_api.storage import FileNotFoundError as StorageFileNotFoundError
from agent_marketplace_api.storage import StorageService, get_storage_service

router = APIRouter()


def get_storage() -> StorageService:
    """Get storage service dependency."""
    return get_storage_service()


StorageDep = Annotated[StorageService, Depends(get_storage)]


@router.get("/{slug}/download")
async def download_latest(
    slug: str,
    agent_service: AgentServiceDep,
    storage: StorageDep,
) -> RedirectResponse:
    """Download the latest version of an agent.

    Redirects to a presigned S3 URL for direct download.
    """
    try:
        agent = await agent_service.get_agent(slug)
    except AgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    # Get the latest version's storage key
    if not agent.versions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No versions available for download",
        )

    latest_version = agent.versions[0]  # Versions should be ordered by date desc
    storage_key = latest_version.storage_key

    try:
        presigned_url = await storage.generate_presigned_download_url(storage_key)
    except StorageFileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent file not found in storage",
        ) from e

    # Increment download counter (fire and forget - don't wait)
    # In production, this would be a background task
    agent.downloads += 1
    await agent_service.repo.update(agent)

    return RedirectResponse(url=presigned_url, status_code=status.HTTP_302_FOUND)


@router.get("/{slug}/download/{version}")
async def download_version(
    slug: str,
    version: str,
    agent_service: AgentServiceDep,
    storage: StorageDep,
) -> RedirectResponse:
    """Download a specific version of an agent.

    Redirects to a presigned S3 URL for direct download.
    """
    try:
        agent = await agent_service.get_agent(slug)
    except AgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    # Find the requested version
    target_version = None
    for v in agent.versions:
        if v.version == version:
            target_version = v
            break

    if not target_version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version} not found for agent '{slug}'",
        )

    try:
        presigned_url = await storage.generate_presigned_download_url(target_version.storage_key)
    except StorageFileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent file not found in storage",
        ) from e

    # Increment download counter
    agent.downloads += 1
    await agent_service.repo.update(agent)

    return RedirectResponse(url=presigned_url, status_code=status.HTTP_302_FOUND)


@router.get("/{slug}/presigned-upload")
async def get_presigned_upload_url(
    slug: str,
    version: str,
    current_user: CurrentUserDep,
    agent_service: AgentServiceDep,
    storage: StorageDep,
) -> dict[str, str]:
    """Get a presigned URL for uploading a new version.

    This allows direct upload to S3/MinIO, bypassing the API server.
    Requires authentication and ownership of the agent.
    """
    try:
        agent = await agent_service.get_agent(slug)
    except AgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    # Check ownership
    if agent.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to upload to this agent",
        )

    # Generate storage key for the new version
    storage_key = f"agents/{current_user.username}/{slug}/{version}.zip"

    presigned_url = await storage.generate_presigned_upload_url(storage_key)

    return {
        "upload_url": presigned_url,
        "storage_key": storage_key,
        "expires_in": "3600",
    }
