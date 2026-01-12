"""Tests for Pydantic schemas."""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from agent_marketplace_api.schemas import (
    AgentCreate,
    AgentListResponse,
    AgentResponse,
    AgentUpdate,
    AgentVersionCreate,
    AgentVersionResponse,
    CategoryCreate,
    CategoryResponse,
    ReviewCreate,
    ReviewResponse,
    ReviewUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from agent_marketplace_api.schemas.agent import AgentSummary
from agent_marketplace_api.schemas.review import ReviewListResponse
from agent_marketplace_api.schemas.user import UserSummary


class TestUserSchemas:
    """Tests for User schemas."""

    def test_user_create_valid(self) -> None:
        """Test valid user creation schema."""
        user = UserCreate(username="testuser", email="test@example.com", github_id=12345)
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.github_id == 12345

    def test_user_create_invalid_email(self) -> None:
        """Test user creation with invalid email."""
        with pytest.raises(ValidationError):
            UserCreate(username="testuser", email="invalid-email", github_id=12345)

    def test_user_create_empty_username(self) -> None:
        """Test user creation with empty username."""
        with pytest.raises(ValidationError):
            UserCreate(username="", email="test@example.com", github_id=12345)

    def test_user_update_optional_fields(self) -> None:
        """Test user update with optional fields."""
        update = UserUpdate(bio="New bio")
        assert update.bio == "New bio"
        assert update.avatar_url is None

    def test_user_response_from_attributes(self) -> None:
        """Test UserResponse from_attributes config."""
        now = datetime.utcnow()
        data = {
            "id": 1,
            "github_id": 12345,
            "username": "testuser",
            "email": "test@example.com",
            "avatar_url": None,
            "bio": None,
            "reputation": 100,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        response = UserResponse.model_validate(data)
        assert response.id == 1
        assert response.reputation == 100

    def test_user_summary(self) -> None:
        """Test UserSummary schema."""
        summary = UserSummary(id=1, username="testuser", avatar_url=None)
        assert summary.id == 1
        assert summary.username == "testuser"


class TestAgentSchemas:
    """Tests for Agent schemas."""

    def test_agent_create_valid(self) -> None:
        """Test valid agent creation schema."""
        agent = AgentCreate(
            name="Test Agent",
            description="A test agent for testing purposes",
            category="testing",
            version="1.0.0",
        )
        assert agent.name == "Test Agent"
        assert agent.version == "1.0.0"

    def test_agent_create_short_name(self) -> None:
        """Test agent creation with too short name."""
        with pytest.raises(ValidationError):
            AgentCreate(
                name="AB",
                description="A test agent for testing",
                category="testing",
                version="1.0.0",
            )

    def test_agent_create_short_description(self) -> None:
        """Test agent creation with too short description."""
        with pytest.raises(ValidationError):
            AgentCreate(
                name="Test Agent",
                description="Short",
                category="testing",
                version="1.0.0",
            )

    def test_agent_create_invalid_version(self) -> None:
        """Test agent creation with invalid version format."""
        with pytest.raises(ValidationError):
            AgentCreate(
                name="Test Agent",
                description="A test agent for testing",
                category="testing",
                version="v1.0",
            )

    def test_agent_update_partial(self) -> None:
        """Test agent update with partial fields."""
        update = AgentUpdate(description="Updated description text")
        assert update.name is None
        assert update.description == "Updated description text"
        assert update.is_public is None

    def test_agent_version_create_valid(self) -> None:
        """Test valid agent version creation."""
        version = AgentVersionCreate(version="2.0.0", changelog="New features")
        assert version.version == "2.0.0"
        assert version.changelog == "New features"

    def test_agent_version_response(self) -> None:
        """Test AgentVersionResponse schema."""
        now = datetime.utcnow()
        response = AgentVersionResponse(
            id=1,
            version="1.0.0",
            changelog="Initial release",
            size_bytes=1024,
            tested=True,
            security_scan_passed=True,
            quality_score=Decimal("0.95"),
            published_at=now,
        )
        assert response.version == "1.0.0"
        assert response.tested is True

    def test_agent_response(self) -> None:
        """Test AgentResponse schema."""
        now = datetime.utcnow()
        response = AgentResponse(
            id=1,
            name="Test Agent",
            slug="test-agent",
            description="Test description",
            author=UserSummary(id=1, username="author"),
            current_version="1.0.0",
            downloads=100,
            stars=50,
            rating=Decimal("4.50"),
            is_public=True,
            is_validated=True,
            created_at=now,
            updated_at=now,
            versions=[],
        )
        assert response.slug == "test-agent"
        assert response.rating == Decimal("4.50")

    def test_agent_summary(self) -> None:
        """Test AgentSummary schema."""
        now = datetime.utcnow()
        summary = AgentSummary(
            id=1,
            name="Test",
            slug="test",
            description="Test agent",
            author=UserSummary(id=1, username="author"),
            current_version="1.0.0",
            downloads=0,
            stars=0,
            rating=Decimal("0.00"),
            is_validated=False,
            created_at=now,
        )
        assert summary.slug == "test"

    def test_agent_list_response(self) -> None:
        """Test AgentListResponse schema."""
        response = AgentListResponse(
            items=[],
            total=0,
            limit=20,
            offset=0,
            has_more=False,
        )
        assert response.total == 0
        assert response.has_more is False


class TestCategorySchemas:
    """Tests for Category schemas."""

    def test_category_create_valid(self) -> None:
        """Test valid category creation."""
        category = CategoryCreate(
            name="Project Management",
            slug="pm",
            icon="clipboard",
            description="Task tracking agents",
        )
        assert category.name == "Project Management"
        assert category.slug == "pm"

    def test_category_create_minimal(self) -> None:
        """Test category creation with minimal fields."""
        category = CategoryCreate(name="Testing", slug="testing")
        assert category.icon is None
        assert category.description is None

    def test_category_response(self) -> None:
        """Test CategoryResponse schema."""
        response = CategoryResponse(
            id=1,
            name="Testing",
            slug="testing",
            icon="test",
            description="Test agents",
            agent_count=5,
        )
        assert response.id == 1
        assert response.agent_count == 5


class TestReviewSchemas:
    """Tests for Review schemas."""

    def test_review_create_valid(self) -> None:
        """Test valid review creation."""
        review = ReviewCreate(rating=5, comment="Excellent!")
        assert review.rating == 5
        assert review.comment == "Excellent!"

    def test_review_create_rating_too_low(self) -> None:
        """Test review creation with rating too low."""
        with pytest.raises(ValidationError):
            ReviewCreate(rating=0, comment="Bad")

    def test_review_create_rating_too_high(self) -> None:
        """Test review creation with rating too high."""
        with pytest.raises(ValidationError):
            ReviewCreate(rating=6, comment="Great")

    def test_review_create_no_comment(self) -> None:
        """Test review creation without comment."""
        review = ReviewCreate(rating=4)
        assert review.comment is None

    def test_review_update_partial(self) -> None:
        """Test review update with partial fields."""
        update = ReviewUpdate(rating=3)
        assert update.rating == 3
        assert update.comment is None

    def test_review_update_invalid_rating(self) -> None:
        """Test review update with invalid rating."""
        with pytest.raises(ValidationError):
            ReviewUpdate(rating=10)

    def test_review_response(self) -> None:
        """Test ReviewResponse schema."""
        now = datetime.utcnow()
        response = ReviewResponse(
            id=1,
            agent_id=1,
            rating=5,
            comment="Great!",
            user=UserSummary(id=1, username="reviewer"),
            helpful_count=10,
            created_at=now,
            updated_at=now,
        )
        assert response.rating == 5
        assert response.helpful_count == 10

    def test_review_list_response(self) -> None:
        """Test ReviewListResponse schema."""
        response = ReviewListResponse(
            items=[],
            total=0,
            average_rating=0.0,
        )
        assert response.total == 0
        assert response.average_rating == 0.0
