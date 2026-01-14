"""Integration tests for admin API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from agent_marketplace_api.models import Agent, AgentVersion, Category, User, agent_categories
from agent_marketplace_api.security import create_access_token


def get_auth_header(user: User) -> dict[str, str]:
    """Get authorization header for a user."""
    token = create_access_token({"sub": str(user.id), "username": user.username})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create admin user."""
    user = User(
        github_id=999,
        username="admin",
        email="admin@example.com",
        role="admin",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def regular_user(db_session: AsyncSession) -> User:
    """Create regular user."""
    user = User(
        github_id=888,
        username="regular",
        email="regular@example.com",
        role="user",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.fixture
async def test_category(db_session: AsyncSession) -> Category:
    """Create test category."""
    category = Category(
        name="Test Category",
        slug="test-category",
        icon="test",
        description="Test description",
        agent_count=0,
    )
    db_session.add(category)
    await db_session.commit()
    return category


@pytest.fixture
async def test_agent_with_category(
    db_session: AsyncSession,
    admin_user: User,
    test_category: Category,
) -> Agent:
    """Create test agent with category."""
    agent = Agent(
        name="Test Agent",
        slug="test-agent",
        description="A test agent for admin testing",
        author_id=admin_user.id,
        current_version="1.0.0",
        is_public=True,
        is_validated=False,
    )
    db_session.add(agent)
    await db_session.flush()

    version = AgentVersion(
        agent_id=agent.id,
        version="1.0.0",
        storage_key="agents/test-agent/1.0.0.zip",
    )
    db_session.add(version)

    # Add agent to category
    await db_session.execute(
        insert(agent_categories).values(agent_id=agent.id, category_id=test_category.id)
    )
    test_category.agent_count = 1

    await db_session.commit()
    return agent


@pytest.mark.integration
class TestAdminCategories:
    """Integration tests for admin category endpoints."""

    @pytest.mark.asyncio
    async def test_create_category_success(
        self, client: AsyncClient, admin_user: User
    ) -> None:
        """Test admin can create a category."""
        response = await client.post(
            "/api/v1/admin/categories",
            json={
                "name": "New Category",
                "slug": "new-category",
                "icon": "star",
                "description": "A new category",
            },
            headers=get_auth_header(admin_user),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Category"
        assert data["slug"] == "new-category"

    @pytest.mark.asyncio
    async def test_create_category_unauthorized(self, client: AsyncClient) -> None:
        """Test unauthenticated user cannot create category."""
        response = await client.post(
            "/api/v1/admin/categories",
            json={"name": "Test", "slug": "test"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_category_forbidden(
        self, client: AsyncClient, regular_user: User
    ) -> None:
        """Test non-admin user cannot create category."""
        response = await client.post(
            "/api/v1/admin/categories",
            json={"name": "Test", "slug": "test"},
            headers=get_auth_header(regular_user),
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_category_success(
        self, client: AsyncClient, admin_user: User, test_category: Category
    ) -> None:
        """Test admin can update a category."""
        response = await client.put(
            f"/api/v1/admin/categories/{test_category.slug}",
            json={"name": "Updated Category", "description": "Updated description"},
            headers=get_auth_header(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Category"
        assert data["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_delete_category_success(
        self, client: AsyncClient, admin_user: User, test_category: Category
    ) -> None:
        """Test admin can delete an empty category."""
        response = await client.delete(
            f"/api/v1/admin/categories/{test_category.slug}",
            headers=get_auth_header(admin_user),
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_category_with_agents_fails(
        self,
        client: AsyncClient,
        admin_user: User,
        test_agent_with_category: Agent,  # noqa: ARG002
        test_category: Category,
    ) -> None:
        """Test cannot delete category with agents."""
        response = await client.delete(
            f"/api/v1/admin/categories/{test_category.slug}",
            headers=get_auth_header(admin_user),
        )

        assert response.status_code == 400
        assert "agent" in response.json()["detail"].lower()


@pytest.mark.integration
class TestAdminAgents:
    """Integration tests for admin agent endpoints."""

    @pytest.mark.asyncio
    async def test_list_agents_admin(
        self,
        client: AsyncClient,
        admin_user: User,
        test_agent_with_category: Agent,  # noqa: ARG002
    ) -> None:
        """Test admin can list all agents."""
        response = await client.get(
            "/api/v1/admin/agents",
            headers=get_auth_header(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["slug"] == "test-agent"
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_list_agents_admin_unauthorized(self, client: AsyncClient) -> None:
        """Test unauthenticated user cannot list admin agents."""
        response = await client.get("/api/v1/admin/agents")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_agents_admin_forbidden(
        self, client: AsyncClient, regular_user: User
    ) -> None:
        """Test non-admin user cannot list admin agents."""
        response = await client.get(
            "/api/v1/admin/agents",
            headers=get_auth_header(regular_user),
        )

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_update_agent_admin(
        self,
        client: AsyncClient,
        admin_user: User,
        test_agent_with_category: Agent,
    ) -> None:
        """Test admin can update an agent."""
        response = await client.put(
            f"/api/v1/admin/agents/{test_agent_with_category.slug}",
            json={
                "name": "Updated Agent Name",
                "description": "Updated description for test",
                "is_validated": True,
            },
            headers=get_auth_header(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Agent Name"
        assert data["is_validated"] is True

    @pytest.mark.asyncio
    async def test_update_agent_category(
        self,
        client: AsyncClient,
        admin_user: User,
        test_agent_with_category: Agent,
        db_session: AsyncSession,
    ) -> None:
        """Test admin can change agent category."""
        # Create a new category
        new_category = Category(
            name="New Category",
            slug="new-category",
            agent_count=0,
        )
        db_session.add(new_category)
        await db_session.commit()

        response = await client.put(
            f"/api/v1/admin/agents/{test_agent_with_category.slug}",
            json={"category": "new-category"},
            headers=get_auth_header(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "new-category"

    @pytest.mark.asyncio
    async def test_delete_agent_admin(
        self,
        client: AsyncClient,
        admin_user: User,
        test_agent_with_category: Agent,
    ) -> None:
        """Test admin can delete an agent."""
        response = await client.delete(
            f"/api/v1/admin/agents/{test_agent_with_category.slug}",
            headers=get_auth_header(admin_user),
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_bulk_update_category(
        self,
        client: AsyncClient,
        admin_user: User,
        test_agent_with_category: Agent,
        db_session: AsyncSession,
    ) -> None:
        """Test admin can bulk move agents to category."""
        # Create a new category
        new_category = Category(
            name="Bulk Category",
            slug="bulk-category",
            agent_count=0,
        )
        db_session.add(new_category)
        await db_session.commit()

        response = await client.post(
            "/api/v1/admin/agents/bulk-category",
            json={
                "agent_slugs": [test_agent_with_category.slug],
                "new_category": "bulk-category",
            },
            headers=get_auth_header(admin_user),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["updated"] == 1
