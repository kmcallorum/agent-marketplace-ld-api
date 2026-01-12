"""User service for user-related business logic."""

from agent_marketplace_api.auth import GitHubUser
from agent_marketplace_api.models import User
from agent_marketplace_api.repositories.user_repo import UserRepository


class UserNotFoundError(Exception):
    """Raised when a user is not found."""

    pass


class UserService:
    """Service for user business logic."""

    def __init__(self, user_repo: UserRepository) -> None:
        """Initialize service with repository."""
        self.repo = user_repo

    async def get_user_by_id(self, user_id: int) -> User:
        """Get user by ID."""
        user = await self.repo.get(user_id)
        if not user:
            raise UserNotFoundError(f"User with ID {user_id} not found")
        return user

    async def get_or_create_from_github(self, github_user: GitHubUser) -> User:
        """Get existing user or create new one from GitHub OAuth."""
        user = await self.repo.find_by_github_id(github_user.id)

        if user:
            # Update user info from GitHub
            user.username = github_user.login
            if github_user.email:
                user.email = github_user.email
            if github_user.avatar_url:
                user.avatar_url = github_user.avatar_url
            return await self.repo.update(user)

        # Create new user
        email = github_user.email or f"{github_user.login}@github.placeholder"
        user = User(
            github_id=github_user.id,
            username=github_user.login,
            email=email,
            avatar_url=github_user.avatar_url,
            bio=github_user.name,
        )
        return await self.repo.create(user)
