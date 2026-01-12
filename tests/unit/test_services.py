"""Tests for service layer."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_marketplace_api.models import Agent, User
from agent_marketplace_api.schemas import AgentCreate, AgentUpdate
from agent_marketplace_api.services.agent_service import (
    AgentAlreadyExistsError,
    AgentListResult,
    AgentNotFoundError,
    AgentPermissionError,
    AgentService,
)


class TestAgentListResult:
    """Tests for AgentListResult dataclass."""

    def test_has_more_true(self) -> None:
        """Test has_more returns True when more results exist."""
        result = AgentListResult(
            items=[MagicMock()],
            total=10,
            limit=5,
            offset=0,
        )
        assert result.has_more is True

    def test_has_more_false(self) -> None:
        """Test has_more returns False when no more results."""
        result = AgentListResult(
            items=[MagicMock()] * 5,
            total=5,
            limit=5,
            offset=0,
        )
        assert result.has_more is False


class TestAgentService:
    """Tests for AgentService."""

    @pytest.fixture
    def mock_repo(self) -> MagicMock:
        """Create mock repository."""
        repo = MagicMock()
        repo.db = MagicMock()
        return repo

    @pytest.fixture
    def mock_user(self) -> User:
        """Create mock user."""
        user = User(
            id=1,
            github_id=123,
            username="testuser",
            email="test@example.com",
        )
        return user

    @pytest.fixture
    def mock_agent(self, mock_user: User) -> Agent:
        """Create mock agent."""
        agent = Agent(
            id=1,
            name="Test Agent",
            slug="test-agent",
            description="A test agent",
            author_id=mock_user.id,
            current_version="1.0.0",
        )
        return agent

    @pytest.mark.asyncio
    async def test_list_agents(self, mock_repo: MagicMock, mock_agent: Agent) -> None:
        """Test listing agents."""
        mock_repo.list_public = AsyncMock(return_value=[mock_agent])
        mock_repo.count_public = AsyncMock(return_value=1)

        service = AgentService(mock_repo)
        result = await service.list_agents(limit=20, offset=0)

        assert len(result.items) == 1
        assert result.total == 1
        mock_repo.list_public.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_agents_with_category(self, mock_repo: MagicMock) -> None:
        """Test listing agents with category filter."""
        mock_repo.list_public = AsyncMock(return_value=[])
        mock_repo.count_public = AsyncMock(return_value=0)

        service = AgentService(mock_repo)
        await service.list_agents(category="testing")

        mock_repo.list_public.assert_called_once_with(
            limit=20, offset=0, category="testing", sort_by="created_at"
        )

    @pytest.mark.asyncio
    async def test_get_agent_found(self, mock_repo: MagicMock, mock_agent: Agent) -> None:
        """Test getting agent by slug when it exists."""
        mock_repo.find_by_slug = AsyncMock(return_value=mock_agent)

        service = AgentService(mock_repo)
        result = await service.get_agent("test-agent")

        assert result.slug == "test-agent"

    @pytest.mark.asyncio
    async def test_get_agent_not_found(self, mock_repo: MagicMock) -> None:
        """Test getting agent raises error when not found."""
        mock_repo.find_by_slug = AsyncMock(return_value=None)

        service = AgentService(mock_repo)

        with pytest.raises(AgentNotFoundError):
            await service.get_agent("nonexistent")

    @pytest.mark.asyncio
    async def test_get_agent_by_id_found(self, mock_repo: MagicMock, mock_agent: Agent) -> None:
        """Test getting agent by ID when it exists."""
        mock_repo.get = AsyncMock(return_value=mock_agent)

        service = AgentService(mock_repo)
        result = await service.get_agent_by_id(1)

        assert result.id == 1

    @pytest.mark.asyncio
    async def test_get_agent_by_id_not_found(self, mock_repo: MagicMock) -> None:
        """Test getting agent by ID raises error when not found."""
        mock_repo.get = AsyncMock(return_value=None)

        service = AgentService(mock_repo)

        with pytest.raises(AgentNotFoundError):
            await service.get_agent_by_id(99999)

    @pytest.mark.asyncio
    async def test_create_agent(self, mock_repo: MagicMock, mock_user: User) -> None:
        """Test creating a new agent."""
        mock_repo.slug_exists = AsyncMock(return_value=False)
        mock_repo.create = AsyncMock(side_effect=lambda a: setattr(a, "id", 1) or a)
        mock_repo.db.add = MagicMock()
        mock_repo.db.flush = AsyncMock()

        service = AgentService(mock_repo)
        data = AgentCreate(
            name="New Agent",
            description="A brand new agent",
            category="testing",
            version="1.0.0",
        )

        result = await service.create_agent(data, mock_user, "storage/key")

        assert result.name == "New Agent"
        assert result.slug == "new-agent"
        mock_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_agent_with_duplicate_slug(
        self, mock_repo: MagicMock, mock_user: User
    ) -> None:
        """Test creating agent generates unique slug when duplicate exists."""
        # First call returns True (slug exists), second returns False
        mock_repo.slug_exists = AsyncMock(side_effect=[True, False])
        mock_repo.create = AsyncMock(side_effect=lambda a: setattr(a, "id", 1) or a)
        mock_repo.db.add = MagicMock()
        mock_repo.db.flush = AsyncMock()

        service = AgentService(mock_repo)
        data = AgentCreate(
            name="Test Agent",
            description="A test agent description",
            category="testing",
            version="1.0.0",
        )

        result = await service.create_agent(data, mock_user, "storage/key")

        assert result.slug == "test-agent-1"

    @pytest.mark.asyncio
    async def test_update_agent_success(
        self, mock_repo: MagicMock, mock_user: User, mock_agent: Agent
    ) -> None:
        """Test updating agent metadata."""
        mock_repo.find_by_slug = AsyncMock(return_value=mock_agent)
        mock_repo.update = AsyncMock(return_value=mock_agent)

        service = AgentService(mock_repo)
        data = AgentUpdate(description="Updated description")

        result = await service.update_agent("test-agent", data, mock_user)

        assert result.description == "Updated description"

    @pytest.mark.asyncio
    async def test_update_agent_not_owner(self, mock_repo: MagicMock, mock_agent: Agent) -> None:
        """Test updating agent fails when user is not owner."""
        mock_repo.find_by_slug = AsyncMock(return_value=mock_agent)

        other_user = User(id=999, github_id=999, username="other", email="other@example.com")

        service = AgentService(mock_repo)
        data = AgentUpdate(description="Updated description text")

        with pytest.raises(AgentPermissionError):
            await service.update_agent("test-agent", data, other_user)

    @pytest.mark.asyncio
    async def test_update_agent_partial(
        self, mock_repo: MagicMock, mock_user: User, mock_agent: Agent
    ) -> None:
        """Test updating agent with partial data."""
        mock_repo.find_by_slug = AsyncMock(return_value=mock_agent)
        mock_repo.update = AsyncMock(return_value=mock_agent)

        service = AgentService(mock_repo)
        data = AgentUpdate(name="New Name", is_public=False)

        await service.update_agent("test-agent", data, mock_user)

        assert mock_agent.name == "New Name"
        assert mock_agent.is_public is False

    @pytest.mark.asyncio
    async def test_delete_agent_success(
        self, mock_repo: MagicMock, mock_user: User, mock_agent: Agent
    ) -> None:
        """Test deleting an agent."""
        mock_repo.find_by_slug = AsyncMock(return_value=mock_agent)
        mock_repo.delete = AsyncMock()

        service = AgentService(mock_repo)
        await service.delete_agent("test-agent", mock_user)

        mock_repo.delete.assert_called_once_with(mock_agent)

    @pytest.mark.asyncio
    async def test_delete_agent_not_owner(self, mock_repo: MagicMock, mock_agent: Agent) -> None:
        """Test deleting agent fails when user is not owner."""
        mock_repo.find_by_slug = AsyncMock(return_value=mock_agent)

        other_user = User(id=999, github_id=999, username="other", email="other@example.com")

        service = AgentService(mock_repo)

        with pytest.raises(AgentPermissionError):
            await service.delete_agent("test-agent", other_user)

    @pytest.mark.asyncio
    async def test_get_user_agents(self, mock_repo: MagicMock, mock_agent: Agent) -> None:
        """Test getting all agents by a user."""
        mock_repo.find_by_author = AsyncMock(return_value=[mock_agent])

        service = AgentService(mock_repo)
        result = await service.get_user_agents(1)

        assert len(result) == 1
        mock_repo.find_by_author.assert_called_once_with(1, limit=20, offset=0)

    def test_generate_slug_simple(self, mock_repo: MagicMock) -> None:
        """Test slug generation from simple name."""
        service = AgentService(mock_repo)
        slug = service._generate_slug("Test Agent")

        assert slug == "test-agent"

    def test_generate_slug_special_chars(self, mock_repo: MagicMock) -> None:
        """Test slug generation removes special characters."""
        service = AgentService(mock_repo)
        slug = service._generate_slug("Test! Agent? #1")

        assert slug == "test-agent-1"

    def test_generate_slug_multiple_spaces(self, mock_repo: MagicMock) -> None:
        """Test slug generation handles multiple spaces."""
        service = AgentService(mock_repo)
        slug = service._generate_slug("Test   Agent")

        assert slug == "test-agent"


class TestExceptions:
    """Tests for service exceptions."""

    def test_agent_not_found_error(self) -> None:
        """Test AgentNotFoundError can be raised."""
        with pytest.raises(AgentNotFoundError):
            raise AgentNotFoundError("Agent not found")

    def test_agent_already_exists_error(self) -> None:
        """Test AgentAlreadyExistsError can be raised."""
        with pytest.raises(AgentAlreadyExistsError):
            raise AgentAlreadyExistsError("Agent exists")

    def test_agent_permission_error(self) -> None:
        """Test AgentPermissionError can be raised."""
        with pytest.raises(AgentPermissionError):
            raise AgentPermissionError("Permission denied")
