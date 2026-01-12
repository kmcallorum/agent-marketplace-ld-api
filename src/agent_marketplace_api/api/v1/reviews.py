"""Review API endpoints."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from agent_marketplace_api.api.deps import CurrentUserDep, ReviewServiceDep
from agent_marketplace_api.schemas.review import (
    ReviewCreate,
    ReviewListResponse,
    ReviewResponse,
    ReviewUpdate,
)
from agent_marketplace_api.schemas.user import UserSummary
from agent_marketplace_api.services.review_service import (
    AgentNotFoundError,
    AlreadyStarredError,
    CannotReviewOwnAgentError,
    NotReviewOwnerError,
    NotStarredError,
    ReviewAlreadyExistsError,
    ReviewNotFoundError,
)

router = APIRouter()


@router.get("/agents/{slug}/reviews", response_model=ReviewListResponse)
async def list_reviews(
    slug: str,
    service: ReviewServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: Annotated[str, Query()] = "helpful",
) -> ReviewListResponse:
    """List reviews for an agent with pagination and sorting.

    Sort options: helpful (default), recent, rating
    """
    try:
        result = await service.get_reviews(slug, limit=limit, offset=offset, sort=sort)
    except AgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

    return ReviewListResponse(
        items=[
            ReviewResponse(
                id=review.id,
                agent_id=review.agent_id,
                user=UserSummary(
                    id=review.user.id,
                    username=review.user.username,
                    avatar_url=review.user.avatar_url,
                ),
                rating=review.rating,
                comment=review.comment,
                helpful_count=review.helpful_count,
                created_at=review.created_at,
                updated_at=review.updated_at,
            )
            for review in result.items
        ],
        total=result.total,
        average_rating=result.average_rating,
    )


@router.post(
    "/agents/{slug}/reviews",
    response_model=ReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_review(
    slug: str,
    data: ReviewCreate,
    current_user: CurrentUserDep,
    service: ReviewServiceDep,
) -> ReviewResponse:
    """Create a review for an agent (requires authentication).

    A user can only leave one review per agent.
    Users cannot review their own agents.
    """
    try:
        review = await service.create_review(slug, data, current_user)
    except AgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except CannotReviewOwnAgentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except ReviewAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    return ReviewResponse(
        id=review.id,
        agent_id=review.agent_id,
        user=UserSummary(
            id=review.user.id,
            username=review.user.username,
            avatar_url=review.user.avatar_url,
        ),
        rating=review.rating,
        comment=review.comment,
        helpful_count=review.helpful_count,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


@router.put("/reviews/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: int,
    data: ReviewUpdate,
    current_user: CurrentUserDep,
    service: ReviewServiceDep,
) -> ReviewResponse:
    """Update a review (requires authentication, must be owner)."""
    try:
        review = await service.update_review(review_id, data, current_user)
    except ReviewNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except NotReviewOwnerError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e

    return ReviewResponse(
        id=review.id,
        agent_id=review.agent_id,
        user=UserSummary(
            id=review.user.id,
            username=review.user.username,
            avatar_url=review.user.avatar_url,
        ),
        rating=review.rating,
        comment=review.comment,
        helpful_count=review.helpful_count,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: int,
    current_user: CurrentUserDep,
    service: ReviewServiceDep,
) -> None:
    """Delete a review (requires authentication, must be owner)."""
    try:
        await service.delete_review(review_id, current_user)
    except ReviewNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except NotReviewOwnerError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e


@router.post("/reviews/{review_id}/helpful", status_code=status.HTTP_204_NO_CONTENT)
async def mark_helpful(
    review_id: int,
    current_user: CurrentUserDep,
    service: ReviewServiceDep,
) -> None:
    """Mark a review as helpful (requires authentication)."""
    try:
        await service.mark_helpful(review_id, current_user)
    except ReviewNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


# Star endpoints
@router.post("/agents/{slug}/star", status_code=status.HTTP_204_NO_CONTENT)
async def star_agent(
    slug: str,
    current_user: CurrentUserDep,
    service: ReviewServiceDep,
) -> None:
    """Star an agent (requires authentication)."""
    try:
        await service.star_agent(slug, current_user)
    except AgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except AlreadyStarredError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.delete("/agents/{slug}/star", status_code=status.HTTP_204_NO_CONTENT)
async def unstar_agent(
    slug: str,
    current_user: CurrentUserDep,
    service: ReviewServiceDep,
) -> None:
    """Unstar an agent (requires authentication)."""
    try:
        await service.unstar_agent(slug, current_user)
    except AgentNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except NotStarredError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
