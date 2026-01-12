"""Review service for business logic."""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.models.agent import Agent
from agent_marketplace_api.models.review import Review
from agent_marketplace_api.models.user import User
from agent_marketplace_api.repositories.agent_repo import AgentRepository
from agent_marketplace_api.repositories.review_repo import ReviewRepository, StarRepository
from agent_marketplace_api.schemas.review import ReviewCreate, ReviewUpdate


class ReviewNotFoundError(Exception):
    """Raised when a review is not found."""

    pass


class ReviewAlreadyExistsError(Exception):
    """Raised when a user has already reviewed an agent."""

    pass


class NotReviewOwnerError(Exception):
    """Raised when user tries to modify a review they don't own."""

    pass


class CannotReviewOwnAgentError(Exception):
    """Raised when user tries to review their own agent."""

    pass


class AgentNotFoundError(Exception):
    """Raised when an agent is not found."""

    pass


class AlreadyStarredError(Exception):
    """Raised when user tries to star an already starred agent."""

    pass


class NotStarredError(Exception):
    """Raised when user tries to unstar an agent they haven't starred."""

    pass


@dataclass
class ReviewListResult:
    """Result of listing reviews."""

    items: list[Review]
    total: int
    average_rating: float


class ReviewService:
    """Service for review operations."""

    def __init__(
        self,
        review_repo: ReviewRepository,
        agent_repo: AgentRepository,
        star_repo: StarRepository,
    ) -> None:
        """Initialize service with repositories."""
        self.review_repo = review_repo
        self.agent_repo = agent_repo
        self.star_repo = star_repo

    async def get_reviews(
        self,
        agent_slug: str,
        *,
        limit: int = 20,
        offset: int = 0,
        sort: str = "helpful",
    ) -> ReviewListResult:
        """Get reviews for an agent.

        Args:
            agent_slug: Agent slug
            limit: Maximum number of results
            offset: Number of results to skip
            sort: Sort order (helpful, recent, rating)

        Returns:
            ReviewListResult with items, total, and average rating

        Raises:
            AgentNotFoundError: If agent not found
        """
        agent = await self.agent_repo.find_by_slug(agent_slug)
        if not agent:
            raise AgentNotFoundError(f"Agent '{agent_slug}' not found")

        reviews = await self.review_repo.get_reviews_for_agent(
            agent.id, limit=limit, offset=offset, sort=sort
        )
        total = await self.review_repo.count_for_agent(agent.id)
        avg_rating = await self.review_repo.get_average_rating(agent.id)

        return ReviewListResult(
            items=reviews,
            total=total,
            average_rating=avg_rating,
        )

    async def create_review(
        self,
        agent_slug: str,
        data: ReviewCreate,
        user: User,
    ) -> Review:
        """Create a review for an agent.

        Args:
            agent_slug: Agent slug
            data: Review data
            user: User creating the review

        Returns:
            Created review

        Raises:
            AgentNotFoundError: If agent not found
            CannotReviewOwnAgentError: If user owns the agent
            ReviewAlreadyExistsError: If user already reviewed
        """
        agent = await self.agent_repo.find_by_slug(agent_slug)
        if not agent:
            raise AgentNotFoundError(f"Agent '{agent_slug}' not found")

        # Check if user is trying to review their own agent
        if agent.author_id == user.id:
            raise CannotReviewOwnAgentError("Cannot review your own agent")

        # Check if user already reviewed this agent
        existing = await self.review_repo.get_by_agent_and_user(agent.id, user.id)
        if existing:
            raise ReviewAlreadyExistsError("You have already reviewed this agent")

        # Create review
        review = Review(
            agent_id=agent.id,
            user_id=user.id,
            rating=data.rating,
            comment=data.comment,
        )
        review = await self.review_repo.create(review)

        # Update agent rating
        await self._update_agent_rating(agent)

        # Refresh to get user relationship
        return await self.review_repo.get_with_user(review.id)  # type: ignore[return-value]

    async def update_review(
        self,
        review_id: int,
        data: ReviewUpdate,
        user: User,
    ) -> Review:
        """Update a review.

        Args:
            review_id: Review ID
            data: Update data
            user: User updating the review

        Returns:
            Updated review

        Raises:
            ReviewNotFoundError: If review not found
            NotReviewOwnerError: If user doesn't own the review
        """
        review = await self.review_repo.get_with_user(review_id)
        if not review:
            raise ReviewNotFoundError(f"Review {review_id} not found")

        if review.user_id != user.id:
            raise NotReviewOwnerError("You can only update your own reviews")

        # Update fields
        if data.rating is not None:
            review.rating = data.rating
        if data.comment is not None:
            review.comment = data.comment

        review = await self.review_repo.update(review)

        # Update agent rating if rating changed
        agent = await self.agent_repo.get(review.agent_id)
        if agent:
            await self._update_agent_rating(agent)

        return review

    async def delete_review(
        self,
        review_id: int,
        user: User,
    ) -> None:
        """Delete a review.

        Args:
            review_id: Review ID
            user: User deleting the review

        Raises:
            ReviewNotFoundError: If review not found
            NotReviewOwnerError: If user doesn't own the review
        """
        review = await self.review_repo.get(review_id)
        if not review:
            raise ReviewNotFoundError(f"Review {review_id} not found")

        if review.user_id != user.id:
            raise NotReviewOwnerError("You can only delete your own reviews")

        agent_id = review.agent_id
        await self.review_repo.delete(review)

        # Update agent rating
        agent = await self.agent_repo.get(agent_id)
        if agent:
            await self._update_agent_rating(agent)

    async def mark_helpful(
        self,
        review_id: int,
        user: User,
    ) -> None:
        """Mark a review as helpful.

        Args:
            review_id: Review ID
            user: User marking as helpful

        Raises:
            ReviewNotFoundError: If review not found
        """
        review = await self.review_repo.get(review_id)
        if not review:
            raise ReviewNotFoundError(f"Review {review_id} not found")

        # Can't mark your own review as helpful
        if review.user_id == user.id:
            return

        await self.review_repo.increment_helpful(review_id)

    async def _update_agent_rating(self, agent: Agent) -> None:
        """Update agent rating based on reviews."""
        avg_rating = await self.review_repo.get_average_rating(agent.id)
        agent.rating = Decimal(str(round(avg_rating, 2)))
        await self.agent_repo.update(agent)

    # Star operations

    async def star_agent(
        self,
        agent_slug: str,
        user: User,
    ) -> None:
        """Star an agent.

        Args:
            agent_slug: Agent slug
            user: User starring the agent

        Raises:
            AgentNotFoundError: If agent not found
            AlreadyStarredError: If already starred
        """
        agent = await self.agent_repo.find_by_slug(agent_slug)
        if not agent:
            raise AgentNotFoundError(f"Agent '{agent_slug}' not found")

        if not await self.star_repo.add_star(user.id, agent.id):
            raise AlreadyStarredError("You have already starred this agent")

        await self.star_repo.update_agent_star_count(agent.id)

    async def unstar_agent(
        self,
        agent_slug: str,
        user: User,
    ) -> None:
        """Unstar an agent.

        Args:
            agent_slug: Agent slug
            user: User unstarring the agent

        Raises:
            AgentNotFoundError: If agent not found
            NotStarredError: If not starred
        """
        agent = await self.agent_repo.find_by_slug(agent_slug)
        if not agent:
            raise AgentNotFoundError(f"Agent '{agent_slug}' not found")

        if not await self.star_repo.remove_star(user.id, agent.id):
            raise NotStarredError("You have not starred this agent")

        await self.star_repo.update_agent_star_count(agent.id)

    async def is_starred(
        self,
        agent_slug: str,
        user: User,
    ) -> bool:
        """Check if user has starred an agent.

        Args:
            agent_slug: Agent slug
            user: User to check

        Returns:
            True if starred, False otherwise

        Raises:
            AgentNotFoundError: If agent not found
        """
        agent = await self.agent_repo.find_by_slug(agent_slug)
        if not agent:
            raise AgentNotFoundError(f"Agent '{agent_slug}' not found")

        return await self.star_repo.is_starred(user.id, agent.id)


def get_review_service(db: AsyncSession) -> ReviewService:
    """Factory function to create ReviewService."""
    review_repo = ReviewRepository(db)
    agent_repo = AgentRepository(db)
    star_repo = StarRepository(db)
    return ReviewService(review_repo, agent_repo, star_repo)
