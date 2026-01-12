"""Authentication utilities and GitHub OAuth."""

from dataclasses import dataclass

import httpx

from agent_marketplace_api.config import get_settings

settings = get_settings()


class GitHubOAuthError(Exception):
    """Raised when GitHub OAuth fails."""

    pass


@dataclass
class GitHubUser:
    """GitHub user information from OAuth."""

    id: int
    login: str
    email: str | None
    avatar_url: str | None
    name: str | None


async def exchange_github_code(code: str) -> str:
    """Exchange GitHub OAuth code for access token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )

        if response.status_code != 200:
            raise GitHubOAuthError(f"Failed to exchange code: {response.text}")

        data = response.json()

        if "error" in data:
            raise GitHubOAuthError(f"GitHub OAuth error: {data.get('error_description', data['error'])}")

        access_token = data.get("access_token")
        if not access_token:
            raise GitHubOAuthError("No access token in response")

        return str(access_token)


async def get_github_user(access_token: str) -> GitHubUser:
    """Get user information from GitHub using access token."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )

        if response.status_code != 200:
            raise GitHubOAuthError(f"Failed to get user info: {response.text}")

        data = response.json()

        # Get primary email if not public
        email = data.get("email")
        if not email:
            email = await _get_github_primary_email(client, access_token)

        return GitHubUser(
            id=data["id"],
            login=data["login"],
            email=email,
            avatar_url=data.get("avatar_url"),
            name=data.get("name"),
        )


async def _get_github_primary_email(client: httpx.AsyncClient, access_token: str) -> str | None:
    """Get primary email from GitHub emails endpoint."""
    response = await client.get(
        "https://api.github.com/user/emails",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json",
        },
    )

    if response.status_code != 200:
        return None

    emails = response.json()
    for email_data in emails:
        if email_data.get("primary") and email_data.get("verified"):
            email = email_data.get("email")
            return str(email) if email else None

    return None
