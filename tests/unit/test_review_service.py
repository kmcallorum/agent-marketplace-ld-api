"""Unit tests for review service."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_marketplace_api.models.agent import Agent
from agent_marketplace_api.models.review import Review
from agent_marketplace_api.models.user import User
from agent_marketplace_api.schemas.review import ReviewCreate, ReviewUpdate
from agent_marketplace_api.services.review_service import (
    AgentNotFoundError,
    AlreadyStarredError,
    NotReviewOwnerError,
    NotStarredError,
    ReviewAlreadyExistsError,
    ReviewNotFoundError,
    ReviewService,
)


@pytest.fixture
def mock_review_repo() -> MagicMock:
    """Create mock review repository."""
    return MagicMock()


@pytest.fixture
def mock_agent_repo() -> MagicMock:
    """Create mock agent repository."""
    return MagicMock()


@pytest.fixture
def mock_star_repo() -> MagicMock:
    """Create mock star repository."""
    return MagicMock()


@pytest.fixture
def review_service(
    mock_review_repo: MagicMock,
    mock_agent_repo: MagicMock,
    mock_star_repo: MagicMock,
) -> ReviewService:
    """Create review service with mocked dependencies."""
    return ReviewService(mock_review_repo, mock_agent_repo, mock_star_repo)


@pytest.fixture
def mock_user() -> User:
    """Create mock user."""
    user = MagicMock(spec=User)
    user.id = 1
    user.username = "testuser"
    user.avatar_url = "https://example.com/avatar.png"
    return user


@pytest.fixture
def mock_agent() -> Agent:
    """Create mock agent."""
    agent = MagicMock(spec=Agent)
    agent.id = 1
    agent.slug = "test-agent"
    agent.author_id = 2  # Different from test user
    agent.rating = Decimal("0.00")
    return agent


@pytest.fixture
def mock_review(mock_user: User, mock_agent: Agent) -> Review:
    """Create mock review."""
    review = MagicMock(spec=Review)
    review.id = 1
    review.agent_id = mock_agent.id
    review.user_id = mock_user.id
    review.user = mock_user
    review.rating = 5
    review.comment = "Great agent!"
    review.helpful_count = 0
    return review


class TestGetReviews:
    """Tests for get_reviews method."""

    @pytest.mark.asyncio
    async def test_get_reviews_success(
        self,
        review_service: ReviewService,
        mock_review_repo: MagicMock,
        mock_agent_repo: MagicMock,
        mock_agent: Agent,
        mock_review: Review,
    ) -> None:
        """Test successful review listing."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=mock_agent)
        mock_review_repo.get_reviews_for_agent = AsyncMock(return_value=[mock_review])
        mock_review_repo.count_for_agent = AsyncMock(return_value=1)
        mock_review_repo.get_average_rating = AsyncMock(return_value=5.0)

        result = await review_service.get_reviews("test-agent", limit=20, offset=0)

        assert len(result.items) == 1
        assert result.total == 1
        assert result.average_rating == 5.0

    @pytest.mark.asyncio
    async def test_get_reviews_agent_not_found(
        self,
        review_service: ReviewService,
        mock_agent_repo: MagicMock,
    ) -> None:
        """Test get_reviews with non-existent agent."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=None)

        with pytest.raises(AgentNotFoundError):
            await review_service.get_reviews("non-existent")

    @pytest.mark.asyncio
    async def test_get_reviews_with_sorting(
        self,
        review_service: ReviewService,
        mock_review_repo: MagicMock,
        mock_agent_repo: MagicMock,
        mock_agent: Agent,
    ) -> None:
        """Test get_reviews with different sort options."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=mock_agent)
        mock_review_repo.get_reviews_for_agent = AsyncMock(return_value=[])
        mock_review_repo.count_for_agent = AsyncMock(return_value=0)
        mock_review_repo.get_average_rating = AsyncMock(return_value=0.0)

        await review_service.get_reviews("test-agent", sort="recent")

        mock_review_repo.get_reviews_for_agent.assert_called_with(
            mock_agent.id, limit=20, offset=0, sort="recent"
        )


class TestCreateReview:
    """Tests for create_review method."""

    @pytest.mark.asyncio
    async def test_create_review_success(
        self,
        review_service: ReviewService,
        mock_review_repo: MagicMock,
        mock_agent_repo: MagicMock,
        mock_agent: Agent,
        mock_user: User,
        mock_review: Review,
    ) -> None:
        """Test successful review creation."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=mock_agent)
        mock_review_repo.get_by_agent_and_user = AsyncMock(return_value=None)
        mock_review_repo.create = AsyncMock(return_value=mock_review)
        mock_review_repo.get_with_user = AsyncMock(return_value=mock_review)
        mock_review_repo.get_average_rating = AsyncMock(return_value=5.0)
        mock_agent_repo.update = AsyncMock(return_value=mock_agent)

        data = ReviewCreate(rating=5, comment="Great agent!")
        result = await review_service.create_review("test-agent", data, mock_user)

        assert result == mock_review
        mock_review_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_review_agent_not_found(
        self,
        review_service: ReviewService,
        mock_agent_repo: MagicMock,
        mock_user: User,
    ) -> None:
        """Test create_review with non-existent agent."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=None)

        data = ReviewCreate(rating=5)
        with pytest.raises(AgentNotFoundError):
            await review_service.create_review("non-existent", data, mock_user)

    @pytest.mark.asyncio
    async def test_create_review_already_reviewed(
        self,
        review_service: ReviewService,
        mock_review_repo: MagicMock,
        mock_agent_repo: MagicMock,
        mock_agent: Agent,
        mock_user: User,
        mock_review: Review,
    ) -> None:
        """Test create_review when already reviewed."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=mock_agent)
        mock_review_repo.get_by_agent_and_user = AsyncMock(return_value=mock_review)

        data = ReviewCreate(rating=5)
        with pytest.raises(ReviewAlreadyExistsError):
            await review_service.create_review("test-agent", data, mock_user)


class TestUpdateReview:
    """Tests for update_review method."""

    @pytest.mark.asyncio
    async def test_update_review_success(
        self,
        review_service: ReviewService,
        mock_review_repo: MagicMock,
        mock_agent_repo: MagicMock,
        mock_user: User,
        mock_review: Review,
        mock_agent: Agent,
    ) -> None:
        """Test successful review update."""
        mock_review_repo.get_with_user = AsyncMock(return_value=mock_review)
        mock_review_repo.update = AsyncMock(return_value=mock_review)
        mock_agent_repo.get = AsyncMock(return_value=mock_agent)
        mock_review_repo.get_average_rating = AsyncMock(return_value=4.0)
        mock_agent_repo.update = AsyncMock(return_value=mock_agent)

        data = ReviewUpdate(rating=4, comment="Updated comment")
        result = await review_service.update_review(1, data, mock_user)

        assert result == mock_review

    @pytest.mark.asyncio
    async def test_update_review_not_found(
        self,
        review_service: ReviewService,
        mock_review_repo: MagicMock,
        mock_user: User,
    ) -> None:
        """Test update_review with non-existent review."""
        mock_review_repo.get_with_user = AsyncMock(return_value=None)

        data = ReviewUpdate(rating=4)
        with pytest.raises(ReviewNotFoundError):
            await review_service.update_review(999, data, mock_user)

    @pytest.mark.asyncio
    async def test_update_review_not_owner(
        self,
        review_service: ReviewService,
        mock_review_repo: MagicMock,
        mock_review: Review,
    ) -> None:
        """Test update_review by non-owner."""
        mock_review_repo.get_with_user = AsyncMock(return_value=mock_review)

        other_user = MagicMock(spec=User)
        other_user.id = 999

        data = ReviewUpdate(rating=4)
        with pytest.raises(NotReviewOwnerError):
            await review_service.update_review(1, data, other_user)


class TestDeleteReview:
    """Tests for delete_review method."""

    @pytest.mark.asyncio
    async def test_delete_review_success(
        self,
        review_service: ReviewService,
        mock_review_repo: MagicMock,
        mock_agent_repo: MagicMock,
        mock_user: User,
        mock_review: Review,
        mock_agent: Agent,
    ) -> None:
        """Test successful review deletion."""
        mock_review_repo.get = AsyncMock(return_value=mock_review)
        mock_review_repo.delete = AsyncMock()
        mock_agent_repo.get = AsyncMock(return_value=mock_agent)
        mock_review_repo.get_average_rating = AsyncMock(return_value=0.0)
        mock_agent_repo.update = AsyncMock(return_value=mock_agent)

        await review_service.delete_review(1, mock_user)

        mock_review_repo.delete.assert_called_once_with(mock_review)

    @pytest.mark.asyncio
    async def test_delete_review_not_found(
        self,
        review_service: ReviewService,
        mock_review_repo: MagicMock,
        mock_user: User,
    ) -> None:
        """Test delete_review with non-existent review."""
        mock_review_repo.get = AsyncMock(return_value=None)

        with pytest.raises(ReviewNotFoundError):
            await review_service.delete_review(999, mock_user)

    @pytest.mark.asyncio
    async def test_delete_review_not_owner(
        self,
        review_service: ReviewService,
        mock_review_repo: MagicMock,
        mock_review: Review,
    ) -> None:
        """Test delete_review by non-owner."""
        mock_review_repo.get = AsyncMock(return_value=mock_review)

        other_user = MagicMock(spec=User)
        other_user.id = 999

        with pytest.raises(NotReviewOwnerError):
            await review_service.delete_review(1, other_user)


class TestMarkHelpful:
    """Tests for mark_helpful method."""

    @pytest.mark.asyncio
    async def test_mark_helpful_success(
        self,
        review_service: ReviewService,
        mock_review_repo: MagicMock,
        mock_review: Review,
    ) -> None:
        """Test successful mark as helpful."""
        # Different user marking as helpful
        other_user = MagicMock(spec=User)
        other_user.id = 999

        mock_review_repo.get = AsyncMock(return_value=mock_review)
        mock_review_repo.increment_helpful = AsyncMock()

        await review_service.mark_helpful(1, other_user)

        mock_review_repo.increment_helpful.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_mark_helpful_own_review(
        self,
        review_service: ReviewService,
        mock_review_repo: MagicMock,
        mock_user: User,
        mock_review: Review,
    ) -> None:
        """Test marking own review as helpful (should be ignored)."""
        mock_review_repo.get = AsyncMock(return_value=mock_review)
        mock_review_repo.increment_helpful = AsyncMock()

        await review_service.mark_helpful(1, mock_user)

        # Should not increment for own review
        mock_review_repo.increment_helpful.assert_not_called()

    @pytest.mark.asyncio
    async def test_mark_helpful_not_found(
        self,
        review_service: ReviewService,
        mock_review_repo: MagicMock,
        mock_user: User,
    ) -> None:
        """Test mark_helpful with non-existent review."""
        mock_review_repo.get = AsyncMock(return_value=None)

        with pytest.raises(ReviewNotFoundError):
            await review_service.mark_helpful(999, mock_user)


class TestStarAgent:
    """Tests for star_agent method."""

    @pytest.mark.asyncio
    async def test_star_agent_success(
        self,
        review_service: ReviewService,
        mock_agent_repo: MagicMock,
        mock_star_repo: MagicMock,
        mock_agent: Agent,
        mock_user: User,
    ) -> None:
        """Test successful star."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=mock_agent)
        mock_star_repo.add_star = AsyncMock(return_value=True)
        mock_star_repo.update_agent_star_count = AsyncMock()

        await review_service.star_agent("test-agent", mock_user)

        mock_star_repo.add_star.assert_called_once_with(mock_user.id, mock_agent.id)
        mock_star_repo.update_agent_star_count.assert_called_once_with(mock_agent.id)

    @pytest.mark.asyncio
    async def test_star_agent_not_found(
        self,
        review_service: ReviewService,
        mock_agent_repo: MagicMock,
        mock_user: User,
    ) -> None:
        """Test star_agent with non-existent agent."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=None)

        with pytest.raises(AgentNotFoundError):
            await review_service.star_agent("non-existent", mock_user)

    @pytest.mark.asyncio
    async def test_star_agent_already_starred(
        self,
        review_service: ReviewService,
        mock_agent_repo: MagicMock,
        mock_star_repo: MagicMock,
        mock_agent: Agent,
        mock_user: User,
    ) -> None:
        """Test star_agent when already starred."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=mock_agent)
        mock_star_repo.add_star = AsyncMock(return_value=False)

        with pytest.raises(AlreadyStarredError):
            await review_service.star_agent("test-agent", mock_user)


class TestUnstarAgent:
    """Tests for unstar_agent method."""

    @pytest.mark.asyncio
    async def test_unstar_agent_success(
        self,
        review_service: ReviewService,
        mock_agent_repo: MagicMock,
        mock_star_repo: MagicMock,
        mock_agent: Agent,
        mock_user: User,
    ) -> None:
        """Test successful unstar."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=mock_agent)
        mock_star_repo.remove_star = AsyncMock(return_value=True)
        mock_star_repo.update_agent_star_count = AsyncMock()

        await review_service.unstar_agent("test-agent", mock_user)

        mock_star_repo.remove_star.assert_called_once_with(mock_user.id, mock_agent.id)
        mock_star_repo.update_agent_star_count.assert_called_once_with(mock_agent.id)

    @pytest.mark.asyncio
    async def test_unstar_agent_not_found(
        self,
        review_service: ReviewService,
        mock_agent_repo: MagicMock,
        mock_user: User,
    ) -> None:
        """Test unstar_agent with non-existent agent."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=None)

        with pytest.raises(AgentNotFoundError):
            await review_service.unstar_agent("non-existent", mock_user)

    @pytest.mark.asyncio
    async def test_unstar_agent_not_starred(
        self,
        review_service: ReviewService,
        mock_agent_repo: MagicMock,
        mock_star_repo: MagicMock,
        mock_agent: Agent,
        mock_user: User,
    ) -> None:
        """Test unstar_agent when not starred."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=mock_agent)
        mock_star_repo.remove_star = AsyncMock(return_value=False)

        with pytest.raises(NotStarredError):
            await review_service.unstar_agent("test-agent", mock_user)


class TestIsStarred:
    """Tests for is_starred method."""

    @pytest.mark.asyncio
    async def test_is_starred_true(
        self,
        review_service: ReviewService,
        mock_agent_repo: MagicMock,
        mock_star_repo: MagicMock,
        mock_agent: Agent,
        mock_user: User,
    ) -> None:
        """Test is_starred returns True when starred."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=mock_agent)
        mock_star_repo.is_starred = AsyncMock(return_value=True)

        result = await review_service.is_starred("test-agent", mock_user)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_starred_false(
        self,
        review_service: ReviewService,
        mock_agent_repo: MagicMock,
        mock_star_repo: MagicMock,
        mock_agent: Agent,
        mock_user: User,
    ) -> None:
        """Test is_starred returns False when not starred."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=mock_agent)
        mock_star_repo.is_starred = AsyncMock(return_value=False)

        result = await review_service.is_starred("test-agent", mock_user)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_starred_agent_not_found(
        self,
        review_service: ReviewService,
        mock_agent_repo: MagicMock,
        mock_user: User,
    ) -> None:
        """Test is_starred with non-existent agent."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=None)

        with pytest.raises(AgentNotFoundError):
            await review_service.is_starred("non-existent", mock_user)


class TestGetReviewsSort:
    """Tests for get_reviews method with different sort options."""

    @pytest.mark.asyncio
    async def test_get_reviews_sort_by_rating(
        self,
        review_service: ReviewService,
        mock_review_repo: MagicMock,
        mock_agent_repo: MagicMock,
        mock_agent: Agent,
    ) -> None:
        """Test get_reviews with rating sort."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=mock_agent)
        mock_review_repo.get_reviews_for_agent = AsyncMock(return_value=[])
        mock_review_repo.count_for_agent = AsyncMock(return_value=0)
        mock_review_repo.get_average_rating = AsyncMock(return_value=0.0)

        await review_service.get_reviews("test-agent", sort="rating")

        mock_review_repo.get_reviews_for_agent.assert_called_with(
            mock_agent.id, limit=20, offset=0, sort="rating"
        )

    @pytest.mark.asyncio
    async def test_get_reviews_sort_by_helpful(
        self,
        review_service: ReviewService,
        mock_review_repo: MagicMock,
        mock_agent_repo: MagicMock,
        mock_agent: Agent,
    ) -> None:
        """Test get_reviews with helpful sort (default)."""
        mock_agent_repo.find_by_slug = AsyncMock(return_value=mock_agent)
        mock_review_repo.get_reviews_for_agent = AsyncMock(return_value=[])
        mock_review_repo.count_for_agent = AsyncMock(return_value=0)
        mock_review_repo.get_average_rating = AsyncMock(return_value=0.0)

        await review_service.get_reviews("test-agent", sort="helpful")

        mock_review_repo.get_reviews_for_agent.assert_called_with(
            mock_agent.id, limit=20, offset=0, sort="helpful"
        )


class TestGetReviewServiceFactory:
    """Tests for get_review_service factory function."""

    def test_get_review_service_creates_service(self) -> None:
        """Test that factory creates ReviewService correctly."""
        from agent_marketplace_api.services.review_service import get_review_service

        mock_db = MagicMock()
        service = get_review_service(mock_db)

        assert isinstance(service, ReviewService)
