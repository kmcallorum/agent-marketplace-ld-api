"""Authentication API endpoints."""

from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from agent_marketplace_api.api.deps import CurrentUserDep
from agent_marketplace_api.auth import (
    GitHubOAuthError,
    exchange_github_code,
    get_github_user,
)
from agent_marketplace_api.models import Agent, agent_stars
from agent_marketplace_api.config import get_settings
from agent_marketplace_api.database import get_db
from agent_marketplace_api.repositories.user_repo import UserRepository
from agent_marketplace_api.schemas import UserResponse
from agent_marketplace_api.security import (
    InvalidTokenError,
    TokenExpiredError,
    create_access_token,
    create_refresh_token,
    verify_token,
)
from agent_marketplace_api.services.user_service import UserService

router = APIRouter()
settings = get_settings()


class GitHubAuthRequest(BaseModel):
    """Request body for GitHub OAuth."""

    code: str


class TokenResponse(BaseModel):
    """Response with JWT tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    """Request body for token refresh."""

    refresh_token: str


class AccessTokenResponse(BaseModel):
    """Response with new access token."""

    access_token: str
    token_type: str = "bearer"


@router.get("/github")
async def github_login() -> RedirectResponse:
    """Redirect to GitHub OAuth authorization page."""
    params = {
        "client_id": settings.github_client_id,
        "scope": "read:user user:email",
    }
    github_auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    return RedirectResponse(url=github_auth_url)


@router.get("/github/callback", response_model=TokenResponse)
async def github_callback(
    code: Annotated[str, Query(description="GitHub OAuth authorization code")],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Handle GitHub OAuth callback and return JWT tokens."""
    try:
        # Exchange code for GitHub access token
        github_token = await exchange_github_code(code)

        # Get user info from GitHub
        github_user = await get_github_user(github_token)

        # Get or create user in our database
        user_repo = UserRepository(db)
        user_service = UserService(user_repo)
        user = await user_service.get_or_create_from_github(github_user)

        # Create JWT tokens
        token_data = {"sub": str(user.id), "username": user.username}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user),
        )

    except GitHubOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/github", response_model=TokenResponse)
async def github_auth(
    request: GitHubAuthRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """Authenticate with GitHub OAuth code."""
    try:
        # Exchange code for GitHub access token
        github_token = await exchange_github_code(request.code)

        # Get user info from GitHub
        github_user = await get_github_user(github_token)

        # Get or create user in our database
        user_repo = UserRepository(db)
        user_service = UserService(user_repo)
        user = await user_service.get_or_create_from_github(github_user)

        # Create JWT tokens
        token_data = {"sub": str(user.id), "username": user.username}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user),
        )

    except GitHubOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(
    request: RefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AccessTokenResponse:
    """Refresh access token using refresh token."""
    try:
        payload = verify_token(request.refresh_token, token_type="refresh")
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        # Verify user still exists
        user_repo = UserRepository(db)
        user = await user_repo.get(int(user_id))

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        # Create new access token
        token_data = {"sub": str(user.id), "username": user.username}
        access_token = create_access_token(token_data)

        return AccessTokenResponse(access_token=access_token)

    except TokenExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        ) from e
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from e


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> None:
    """Logout user (client should discard tokens)."""
    # JWT tokens are stateless, so logout is handled client-side
    # In a production app, you might want to blacklist the token
    return None


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: CurrentUserDep) -> UserResponse:
    """Get current authenticated user information."""
    return UserResponse.model_validate(current_user)


class StarredAgentsResponse(BaseModel):
    """Response with user's starred agent slugs."""

    starred: list[str]


@router.get("/me/starred", response_model=StarredAgentsResponse)
async def get_starred_agents(
    current_user: CurrentUserDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StarredAgentsResponse:
    """Get current user's starred agent slugs."""
    result = await db.execute(
        select(Agent.slug)
        .join(agent_stars, agent_stars.c.agent_id == Agent.id)
        .where(agent_stars.c.user_id == current_user.id)
    )
    slugs = [row[0] for row in result.all()]
    return StarredAgentsResponse(starred=slugs)
