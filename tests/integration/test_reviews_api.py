"""Integration tests for reviews API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.models import User
from agent_marketplace_api.models.agent import Agent
from agent_marketplace_api.models.review import Review
from agent_marketplace_api.security import create_access_token


@pytest.fixture
async def author_user(db_session: AsyncSession) -> User:
    """Create an author user in the database."""
    user = User(
        github_id=10001,
        username="agentauthor",
        email="author@example.com",
        avatar_url="https://example.com/author.png",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def reviewer_user(db_session: AsyncSession) -> User:
    """Create a reviewer user in the database."""
    user = User(
        github_id=10002,
        username="reviewer",
        email="reviewer@example.com",
        avatar_url="https://example.com/reviewer.png",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Create another user in the database."""
    user = User(
        github_id=10003,
        username="otheruser",
        email="other@example.com",
        avatar_url="https://example.com/other.png",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_agent(db_session: AsyncSession, author_user: User) -> Agent:
    """Create a test agent in the database."""
    agent = Agent(
        name="Test Agent",
        slug="test-agent",
        description="A test agent for reviews",
        author_id=author_user.id,
        current_version="1.0.0",
    )
    db_session.add(agent)
    await db_session.flush()
    await db_session.refresh(agent)
    return agent


@pytest.fixture
async def existing_review(
    db_session: AsyncSession, test_agent: Agent, reviewer_user: User
) -> Review:
    """Create an existing review in the database."""
    review = Review(
        agent_id=test_agent.id,
        user_id=reviewer_user.id,
        rating=4,
        comment="Good agent!",
    )
    db_session.add(review)
    await db_session.flush()
    await db_session.refresh(review)
    return review


def get_auth_header(user: User) -> dict[str, str]:
    """Get authorization header for a user."""
    token = create_access_token({"sub": str(user.id), "username": user.username})
    return {"Authorization": f"Bearer {token}"}


class TestListReviews:
    """Tests for GET /api/v1/agents/{slug}/reviews endpoint."""

    @pytest.mark.asyncio
    async def test_list_reviews_success(
        self,
        client: AsyncClient,
        test_agent: Agent,
        existing_review: Review,  # noqa: ARG002
    ) -> None:
        """Test listing reviews for an agent."""
        response = await client.get(f"/api/v1/agents/{test_agent.slug}/reviews")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["rating"] == 4
        assert data["items"][0]["comment"] == "Good agent!"

    @pytest.mark.asyncio
    async def test_list_reviews_empty(
        self,
        client: AsyncClient,
        test_agent: Agent,
    ) -> None:
        """Test listing reviews when none exist."""
        response = await client.get(f"/api/v1/agents/{test_agent.slug}/reviews")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    @pytest.mark.asyncio
    async def test_list_reviews_agent_not_found(
        self,
        client: AsyncClient,
    ) -> None:
        """Test listing reviews for non-existent agent."""
        response = await client.get("/api/v1/agents/non-existent/reviews")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_reviews_with_pagination(
        self,
        client: AsyncClient,
        test_agent: Agent,
        existing_review: Review,  # noqa: ARG002
    ) -> None:
        """Test listing reviews with pagination."""
        response = await client.get(f"/api/v1/agents/{test_agent.slug}/reviews?limit=10&offset=0")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_reviews_sort_recent(
        self,
        client: AsyncClient,
        test_agent: Agent,
        existing_review: Review,  # noqa: ARG002
    ) -> None:
        """Test listing reviews sorted by recent."""
        response = await client.get(f"/api/v1/agents/{test_agent.slug}/reviews?sort=recent")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_reviews_sort_rating(
        self,
        client: AsyncClient,
        test_agent: Agent,
        existing_review: Review,  # noqa: ARG002
    ) -> None:
        """Test listing reviews sorted by rating."""
        response = await client.get(f"/api/v1/agents/{test_agent.slug}/reviews?sort=rating")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1


class TestCreateReview:
    """Tests for POST /api/v1/agents/{slug}/reviews endpoint."""

    @pytest.mark.asyncio
    async def test_create_review_success(
        self,
        client: AsyncClient,
        test_agent: Agent,
        reviewer_user: User,
    ) -> None:
        """Test creating a review."""
        response = await client.post(
            f"/api/v1/agents/{test_agent.slug}/reviews",
            json={"rating": 5, "comment": "Excellent agent!"},
            headers=get_auth_header(reviewer_user),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["rating"] == 5
        assert data["comment"] == "Excellent agent!"
        assert data["user"]["username"] == "reviewer"

    @pytest.mark.asyncio
    async def test_create_review_no_comment(
        self,
        client: AsyncClient,
        test_agent: Agent,
        reviewer_user: User,
    ) -> None:
        """Test creating a review without comment."""
        response = await client.post(
            f"/api/v1/agents/{test_agent.slug}/reviews",
            json={"rating": 3},
            headers=get_auth_header(reviewer_user),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["rating"] == 3
        assert data["comment"] is None

    @pytest.mark.asyncio
    async def test_create_review_unauthorized(
        self,
        client: AsyncClient,
        test_agent: Agent,
    ) -> None:
        """Test creating a review without authentication."""
        response = await client.post(
            f"/api/v1/agents/{test_agent.slug}/reviews",
            json={"rating": 5},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_review_own_agent(
        self,
        client: AsyncClient,
        test_agent: Agent,
        author_user: User,
    ) -> None:
        """Test creating a review for own agent (allowed)."""
        response = await client.post(
            f"/api/v1/agents/{test_agent.slug}/reviews",
            json={"rating": 5},
            headers=get_auth_header(author_user),
        )

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_create_review_already_reviewed(
        self,
        client: AsyncClient,
        test_agent: Agent,
        reviewer_user: User,
        existing_review: Review,  # noqa: ARG002
    ) -> None:
        """Test creating a second review."""
        response = await client.post(
            f"/api/v1/agents/{test_agent.slug}/reviews",
            json={"rating": 5},
            headers=get_auth_header(reviewer_user),
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_create_review_invalid_rating(
        self,
        client: AsyncClient,
        test_agent: Agent,
        reviewer_user: User,
    ) -> None:
        """Test creating a review with invalid rating."""
        response = await client.post(
            f"/api/v1/agents/{test_agent.slug}/reviews",
            json={"rating": 6},
            headers=get_auth_header(reviewer_user),
        )

        assert response.status_code == 422


class TestUpdateReview:
    """Tests for PUT /api/v1/reviews/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_review_success(
        self,
        client: AsyncClient,
        existing_review: Review,
        reviewer_user: User,
    ) -> None:
        """Test updating a review."""
        response = await client.put(
            f"/api/v1/reviews/{existing_review.id}",
            json={"rating": 5, "comment": "Updated comment"},
            headers=get_auth_header(reviewer_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 5
        assert data["comment"] == "Updated comment"

    @pytest.mark.asyncio
    async def test_update_review_not_found(
        self,
        client: AsyncClient,
        reviewer_user: User,
    ) -> None:
        """Test updating a non-existent review."""
        response = await client.put(
            "/api/v1/reviews/99999",
            json={"rating": 5},
            headers=get_auth_header(reviewer_user),
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_review_not_owner(
        self,
        client: AsyncClient,
        existing_review: Review,
        other_user: User,
    ) -> None:
        """Test updating another user's review."""
        response = await client.put(
            f"/api/v1/reviews/{existing_review.id}",
            json={"rating": 5},
            headers=get_auth_header(other_user),
        )

        assert response.status_code == 403


class TestDeleteReview:
    """Tests for DELETE /api/v1/reviews/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_review_success(
        self,
        client: AsyncClient,
        existing_review: Review,
        reviewer_user: User,
    ) -> None:
        """Test deleting a review."""
        response = await client.delete(
            f"/api/v1/reviews/{existing_review.id}",
            headers=get_auth_header(reviewer_user),
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_review_not_found(
        self,
        client: AsyncClient,
        reviewer_user: User,
    ) -> None:
        """Test deleting a non-existent review."""
        response = await client.delete(
            "/api/v1/reviews/99999",
            headers=get_auth_header(reviewer_user),
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_review_not_owner(
        self,
        client: AsyncClient,
        existing_review: Review,
        other_user: User,
    ) -> None:
        """Test deleting another user's review."""
        response = await client.delete(
            f"/api/v1/reviews/{existing_review.id}",
            headers=get_auth_header(other_user),
        )

        assert response.status_code == 403


class TestMarkHelpful:
    """Tests for POST /api/v1/reviews/{id}/helpful endpoint."""

    @pytest.mark.asyncio
    async def test_mark_helpful_success(
        self,
        client: AsyncClient,
        existing_review: Review,
        other_user: User,
    ) -> None:
        """Test marking a review as helpful."""
        response = await client.post(
            f"/api/v1/reviews/{existing_review.id}/helpful",
            headers=get_auth_header(other_user),
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_mark_helpful_not_found(
        self,
        client: AsyncClient,
        other_user: User,
    ) -> None:
        """Test marking non-existent review as helpful."""
        response = await client.post(
            "/api/v1/reviews/99999/helpful",
            headers=get_auth_header(other_user),
        )

        assert response.status_code == 404


class TestStarAgent:
    """Tests for POST /api/v1/agents/{slug}/star endpoint."""

    @pytest.mark.asyncio
    async def test_star_agent_success(
        self,
        client: AsyncClient,
        test_agent: Agent,
        reviewer_user: User,
    ) -> None:
        """Test starring an agent."""
        response = await client.post(
            f"/api/v1/agents/{test_agent.slug}/star",
            headers=get_auth_header(reviewer_user),
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_star_agent_unauthorized(
        self,
        client: AsyncClient,
        test_agent: Agent,
    ) -> None:
        """Test starring an agent without authentication."""
        response = await client.post(
            f"/api/v1/agents/{test_agent.slug}/star",
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_star_agent_not_found(
        self,
        client: AsyncClient,
        reviewer_user: User,
    ) -> None:
        """Test starring a non-existent agent."""
        response = await client.post(
            "/api/v1/agents/non-existent/star",
            headers=get_auth_header(reviewer_user),
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_star_agent_already_starred(
        self,
        client: AsyncClient,
        test_agent: Agent,
        reviewer_user: User,
    ) -> None:
        """Test starring an already starred agent."""
        # Star first time
        await client.post(
            f"/api/v1/agents/{test_agent.slug}/star",
            headers=get_auth_header(reviewer_user),
        )

        # Try to star again
        response = await client.post(
            f"/api/v1/agents/{test_agent.slug}/star",
            headers=get_auth_header(reviewer_user),
        )

        assert response.status_code == 409


class TestUnstarAgent:
    """Tests for DELETE /api/v1/agents/{slug}/star endpoint."""

    @pytest.mark.asyncio
    async def test_unstar_agent_success(
        self,
        client: AsyncClient,
        test_agent: Agent,
        reviewer_user: User,
    ) -> None:
        """Test unstarring an agent."""
        # Star first
        await client.post(
            f"/api/v1/agents/{test_agent.slug}/star",
            headers=get_auth_header(reviewer_user),
        )

        # Then unstar
        response = await client.delete(
            f"/api/v1/agents/{test_agent.slug}/star",
            headers=get_auth_header(reviewer_user),
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_unstar_agent_not_starred(
        self,
        client: AsyncClient,
        test_agent: Agent,
        reviewer_user: User,
    ) -> None:
        """Test unstarring an agent that wasn't starred."""
        response = await client.delete(
            f"/api/v1/agents/{test_agent.slug}/star",
            headers=get_auth_header(reviewer_user),
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_unstar_agent_not_found(
        self,
        client: AsyncClient,
        reviewer_user: User,
    ) -> None:
        """Test unstarring a non-existent agent."""
        response = await client.delete(
            "/api/v1/agents/non-existent/star",
            headers=get_auth_header(reviewer_user),
        )

        assert response.status_code == 404
