"""FastAPI dependencies for dependency injection."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.database import get_db
from agent_marketplace_api.models import User
from agent_marketplace_api.repositories import (
    AgentRepository,
    ReviewRepository,
    StarRepository,
    UserRepository,
)
from agent_marketplace_api.security import InvalidTokenError, TokenExpiredError, verify_token
from agent_marketplace_api.services import AgentService, ReviewService, UserService
from agent_marketplace_api.services.analytics_service import AnalyticsService
from agent_marketplace_api.services.search_service import SearchService

security_scheme = HTTPBearer(auto_error=False, description="JWT token from GitHub OAuth")


async def get_agent_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncGenerator[AgentRepository, None]:
    """Get agent repository."""
    yield AgentRepository(db)


async def get_user_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncGenerator[UserRepository, None]:
    """Get user repository."""
    yield UserRepository(db)


async def get_agent_service(
    repo: Annotated[AgentRepository, Depends(get_agent_repo)],
) -> AsyncGenerator[AgentService, None]:
    """Get agent service."""
    yield AgentService(repo)


async def get_user_service(
    repo: Annotated[UserRepository, Depends(get_user_repo)],
) -> AsyncGenerator[UserService, None]:
    """Get user service."""
    yield UserService(repo)


async def get_review_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncGenerator[ReviewRepository, None]:
    """Get review repository."""
    yield ReviewRepository(db)


async def get_star_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncGenerator[StarRepository, None]:
    """Get star repository."""
    yield StarRepository(db)


async def get_review_service(
    review_repo: Annotated[ReviewRepository, Depends(get_review_repo)],
    agent_repo: Annotated[AgentRepository, Depends(get_agent_repo)],
    star_repo: Annotated[StarRepository, Depends(get_star_repo)],
) -> AsyncGenerator[ReviewService, None]:
    """Get review service."""
    yield ReviewService(review_repo, agent_repo, star_repo)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> User:
    """Get current authenticated user from JWT token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token = credentials.credentials
        payload = verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user = await user_service.get_user_by_id(int(user_id))
        return user
    except TokenExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> User | None:
    """Get current user if authenticated, None otherwise."""
    if not credentials:
        return None

    try:
        token = credentials.credentials
        payload = verify_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        return await user_service.get_user_by_id(int(user_id))
    except (TokenExpiredError, InvalidTokenError, Exception):
        return None


async def get_search_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncGenerator[SearchService, None]:
    """Get search service."""
    yield SearchService(db)


async def get_analytics_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncGenerator[AnalyticsService, None]:
    """Get analytics service."""
    yield AnalyticsService(db)


# Type aliases for cleaner endpoint signatures
AgentRepoDep = Annotated[AgentRepository, Depends(get_agent_repo)]
AgentServiceDep = Annotated[AgentService, Depends(get_agent_service)]
AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]
ReviewServiceDep = Annotated[ReviewService, Depends(get_review_service)]
SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
UserRepoDep = Annotated[UserRepository, Depends(get_user_repo)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
OptionalUserDep = Annotated[User | None, Depends(get_optional_user)]


async def require_admin(current_user: CurrentUserDep) -> User:
    """Require admin role for access."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


AdminUserDep = Annotated[User, Depends(require_admin)]
