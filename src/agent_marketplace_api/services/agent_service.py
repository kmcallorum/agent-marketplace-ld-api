"""Agent service for business logic."""

import re
from dataclasses import dataclass

from agent_marketplace_api.models import Agent, AgentVersion, User
from agent_marketplace_api.repositories import AgentRepository
from agent_marketplace_api.schemas import AgentCreate, AgentUpdate


class AgentNotFoundError(Exception):
    """Raised when an agent is not found."""

    pass


class AgentAlreadyExistsError(Exception):
    """Raised when trying to create an agent with existing slug."""

    pass


class AgentPermissionError(Exception):
    """Raised when user doesn't have permission for an action."""

    pass


@dataclass
class AgentListResult:
    """Result of listing agents with pagination info."""

    items: list[Agent]
    total: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        """Check if there are more results."""
        return self.offset + len(self.items) < self.total


class AgentService:
    """Service for agent business logic."""

    def __init__(self, agent_repo: AgentRepository) -> None:
        """Initialize service with repository."""
        self.repo = agent_repo

    async def list_agents(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        category: str | None = None,
        sort_by: str = "created_at",
    ) -> AgentListResult:
        """List public agents with pagination."""
        agents = await self.repo.list_public(
            limit=limit, offset=offset, category=category, sort_by=sort_by
        )
        total = await self.repo.count_public(category=category)

        return AgentListResult(
            items=agents,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_agent(self, slug: str) -> Agent:
        """Get agent by slug."""
        agent = await self.repo.find_by_slug(slug)
        if not agent:
            raise AgentNotFoundError(f"Agent '{slug}' not found")
        return agent

    async def get_agent_by_id(self, agent_id: int) -> Agent:
        """Get agent by ID."""
        agent = await self.repo.get(agent_id)
        if not agent:
            raise AgentNotFoundError(f"Agent with ID {agent_id} not found")
        return agent

    async def create_agent(
        self,
        data: AgentCreate,
        author: User,
        storage_key: str,
    ) -> Agent:
        """Create a new agent."""
        slug = self._generate_slug(data.name)

        # Check if slug exists, append number if needed
        base_slug = slug
        counter = 1
        while await self.repo.slug_exists(slug):
            slug = f"{base_slug}-{counter}"
            counter += 1

        agent = Agent(
            name=data.name,
            slug=slug,
            description=data.description,
            author_id=author.id,
            current_version=data.version,
        )

        agent = await self.repo.create(agent)

        # Create initial version
        version = AgentVersion(
            agent_id=agent.id,
            version=data.version,
            storage_key=storage_key,
        )
        self.repo.db.add(version)
        await self.repo.db.flush()

        return agent

    async def update_agent(
        self,
        slug: str,
        data: AgentUpdate,
        user: User,
    ) -> Agent:
        """Update an agent's metadata."""
        agent = await self.get_agent(slug)

        if agent.author_id != user.id:
            raise AgentPermissionError("You don't have permission to update this agent")

        if data.name is not None:
            agent.name = data.name
        if data.description is not None:
            agent.description = data.description
        if data.is_public is not None:
            agent.is_public = data.is_public

        return await self.repo.update(agent)

    async def delete_agent(self, slug: str, user: User) -> None:
        """Delete an agent."""
        agent = await self.get_agent(slug)

        if agent.author_id != user.id:
            raise AgentPermissionError("You don't have permission to delete this agent")

        await self.repo.delete(agent)

    async def get_user_agents(
        self,
        author_id: int,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Agent]:
        """Get all agents by a user."""
        return await self.repo.find_by_author(author_id, limit=limit, offset=offset)

    def _generate_slug(self, name: str) -> str:
        """Generate URL-friendly slug from name."""
        slug = name.lower()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug.strip("-")
