# Authentication

GitHub OAuth and JWT-based authentication for agent-marketplace-api.

## Overview

The API uses GitHub OAuth for user authentication and JWT tokens for session management.

```
User → GitHub OAuth → API → JWT Tokens → Protected Endpoints
```

---

## Authentication Flow

### 1. GitHub OAuth Flow

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│ Frontend│     │   API   │     │ GitHub  │     │   DB    │
└────┬────┘     └────┬────┘     └────┬────┘     └────┬────┘
     │               │               │               │
     │ Click Login   │               │               │
     │──────────────▶│               │               │
     │               │               │               │
     │ Redirect URL  │               │               │
     │◀──────────────│               │               │
     │               │               │               │
     │ Redirect to GitHub            │               │
     │──────────────────────────────▶│               │
     │               │               │               │
     │ User Authorizes               │               │
     │◀──────────────────────────────│               │
     │               │               │               │
     │ Callback with code            │               │
     │──────────────▶│               │               │
     │               │               │               │
     │               │ Exchange code │               │
     │               │──────────────▶│               │
     │               │               │               │
     │               │ Access token  │               │
     │               │◀──────────────│               │
     │               │               │               │
     │               │ Get user info │               │
     │               │──────────────▶│               │
     │               │               │               │
     │               │ User data     │               │
     │               │◀──────────────│               │
     │               │               │               │
     │               │ Create/Update │               │
     │               │───────────────────────────────▶
     │               │               │               │
     │               │ User record   │               │
     │               │◀──────────────────────────────│
     │               │               │               │
     │ JWT Tokens    │               │               │
     │◀──────────────│               │               │
     │               │               │               │
```

### 2. Token Refresh Flow

```
Frontend → Refresh Token → API → New Access Token → Frontend
```

---

## Implementation

### GitHub OAuth Configuration

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # GitHub OAuth
    github_client_id: str
    github_client_secret: str
    github_redirect_uri: str = "http://localhost:8000/api/v1/auth/github/callback"
    github_authorize_url: str = "https://github.com/login/oauth/authorize"
    github_token_url: str = "https://github.com/login/oauth/access_token"
    github_api_url: str = "https://api.github.com"

    # JWT Settings
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    model_config = {"env_file": ".env"}

settings = Settings()
```

### Security Module

```python
# security.py
from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
from passlib.context import CryptContext

from agent_marketplace_api.config import settings

# Password hashing (for future use)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes)
    )
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    })
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(data: dict[str, Any]) -> str:
    """Create JWT refresh token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh",
    })
    return jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def verify_token(token: str, token_type: str = "access") -> dict[str, Any]:
    """Verify and decode JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != token_type:
            raise AuthenticationError(f"Invalid token type: expected {token_type}")
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {e}")


def hash_password(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


class AuthenticationError(Exception):
    """Authentication error."""
    pass
```

### GitHub OAuth Handler

```python
# auth.py
import httpx
from dataclasses import dataclass

from agent_marketplace_api.config import settings


@dataclass
class GitHubUser:
    """GitHub user data."""
    id: int
    login: str
    email: str | None
    avatar_url: str | None
    name: str | None
    bio: str | None


class GitHubOAuth:
    """GitHub OAuth handler."""

    def __init__(self):
        self.client_id = settings.github_client_id
        self.client_secret = settings.github_client_secret
        self.redirect_uri = settings.github_redirect_uri

    def get_authorize_url(self, state: str | None = None) -> str:
        """Get GitHub OAuth authorize URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "read:user user:email",
        }
        if state:
            params["state"] = state

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{settings.github_authorize_url}?{query}"

    async def exchange_code(self, code: str) -> str:
        """Exchange OAuth code for access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.github_token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                raise AuthenticationError(f"GitHub OAuth error: {data['error']}")

            return data["access_token"]

    async def get_user(self, access_token: str) -> GitHubUser:
        """Get GitHub user info."""
        async with httpx.AsyncClient() as client:
            # Get user profile
            response = await client.get(
                f"{settings.github_api_url}/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            response.raise_for_status()
            user_data = response.json()

            # Get user email if not public
            email = user_data.get("email")
            if not email:
                email = await self._get_primary_email(client, access_token)

            return GitHubUser(
                id=user_data["id"],
                login=user_data["login"],
                email=email,
                avatar_url=user_data.get("avatar_url"),
                name=user_data.get("name"),
                bio=user_data.get("bio"),
            )

    async def _get_primary_email(
        self,
        client: httpx.AsyncClient,
        access_token: str,
    ) -> str | None:
        """Get user's primary email from GitHub."""
        response = await client.get(
            f"{settings.github_api_url}/user/emails",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        if response.status_code == 200:
            emails = response.json()
            for email in emails:
                if email.get("primary"):
                    return email["email"]
        return None


github_oauth = GitHubOAuth()
```

### Auth Endpoints

```python
# api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from agent_marketplace_api.auth import github_oauth, GitHubUser
from agent_marketplace_api.security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    AuthenticationError,
)
from agent_marketplace_api.dependencies import get_db, get_current_user
from agent_marketplace_api.models import User
from agent_marketplace_api.schemas.auth import (
    GitHubAuthRequest,
    TokenResponse,
    RefreshRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/github/authorize")
async def github_authorize():
    """Get GitHub OAuth authorization URL."""
    url = github_oauth.get_authorize_url()
    return {"authorize_url": url}


@router.post("/github", response_model=TokenResponse)
async def github_callback(
    request: GitHubAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange GitHub OAuth code for JWT tokens.

    This endpoint:
    1. Exchanges the GitHub code for a GitHub access token
    2. Fetches user info from GitHub
    3. Creates or updates user in database
    4. Returns JWT access and refresh tokens
    """
    try:
        # Exchange code for GitHub token
        github_token = await github_oauth.exchange_code(request.code)

        # Get user info from GitHub
        github_user = await github_oauth.get_user(github_token)

        # Create or update user in database
        user = await get_or_create_user(db, github_user)

        # Create JWT tokens
        token_data = {"sub": str(user.id), "username": user.username}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post("/refresh", response_model=dict)
async def refresh_token(request: RefreshRequest):
    """Refresh access token using refresh token."""
    try:
        payload = verify_token(request.refresh_token, token_type="refresh")
        token_data = {"sub": payload["sub"], "username": payload["username"]}
        access_token = create_access_token(token_data)
        return {"access_token": access_token, "token_type": "bearer"}
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout user.

    Note: With stateless JWT, we can't truly invalidate tokens.
    The frontend should discard the tokens.
    For true invalidation, implement a token blacklist in Redis.
    """
    # Optional: Add refresh token to blacklist
    # await redis.sadd("token_blacklist", refresh_token)
    return None


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user."""
    return UserResponse.model_validate(current_user)


async def get_or_create_user(db: AsyncSession, github_user: GitHubUser) -> User:
    """Get existing user or create new one from GitHub data."""
    # Try to find existing user
    result = await db.execute(
        select(User).where(User.github_id == github_user.id)
    )
    user = result.scalar_one_or_none()

    if user:
        # Update user info from GitHub
        user.username = github_user.login
        user.email = github_user.email
        user.avatar_url = github_user.avatar_url
        user.bio = github_user.bio
    else:
        # Create new user
        user = User(
            github_id=github_user.id,
            username=github_user.login,
            email=github_user.email,
            avatar_url=github_user.avatar_url,
            bio=github_user.bio,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)
    return user
```

### Auth Schemas

```python
# schemas/auth.py
from pydantic import BaseModel, EmailStr


class GitHubAuthRequest(BaseModel):
    """GitHub OAuth callback request."""
    code: str


class RefreshRequest(BaseModel):
    """Token refresh request."""
    refresh_token: str


class UserResponse(BaseModel):
    """User response schema."""
    id: int
    username: str
    email: EmailStr | None
    avatar_url: str | None
    bio: str | None
    reputation: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
```

### Dependencies

```python
# dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from agent_marketplace_api.database import async_session_maker
from agent_marketplace_api.models import User
from agent_marketplace_api.security import verify_token, AuthenticationError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/github")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Database session dependency."""
    async with async_session_maker() as session:
        yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = verify_token(token)
        user_id = int(payload.get("sub"))
    except (AuthenticationError, ValueError):
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return user


async def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Get current user if authenticated, None otherwise."""
    if not token:
        return None
    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None
```

---

## JWT Token Structure

### Access Token

```json
{
  "sub": "123",
  "username": "johndoe",
  "exp": 1609459200,
  "iat": 1609455600,
  "type": "access"
}
```

- **sub**: User ID
- **username**: GitHub username
- **exp**: Expiration timestamp
- **iat**: Issued at timestamp
- **type**: Token type (access/refresh)

### Refresh Token

```json
{
  "sub": "123",
  "username": "johndoe",
  "exp": 1610064000,
  "iat": 1609455600,
  "type": "refresh"
}
```

---

## Protected Endpoints

### Requiring Authentication

```python
from fastapi import Depends
from agent_marketplace_api.dependencies import get_current_user
from agent_marketplace_api.models import User

@router.post("/agents")
async def create_agent(
    data: AgentCreate,
    current_user: User = Depends(get_current_user),  # Requires auth
):
    """Create a new agent (authentication required)."""
    # current_user is guaranteed to be authenticated
    agent = await agent_service.create(data, author=current_user)
    return agent
```

### Optional Authentication

```python
from agent_marketplace_api.dependencies import get_current_user_optional

@router.get("/agents/{slug}")
async def get_agent(
    slug: str,
    current_user: User | None = Depends(get_current_user_optional),
):
    """Get agent details (auth optional for additional info)."""
    agent = await agent_service.get_by_slug(slug)

    # Show extra info if user owns the agent
    if current_user and agent.author_id == current_user.id:
        return AgentDetailResponse.with_private_info(agent)

    return AgentDetailResponse.model_validate(agent)
```

---

## Token Blacklisting (Optional)

For true token invalidation, implement a Redis blacklist:

```python
# auth.py
import redis.asyncio as redis

redis_client = redis.from_url(settings.redis_url)


async def blacklist_token(token: str, expires_in: int):
    """Add token to blacklist."""
    await redis_client.setex(f"blacklist:{token}", expires_in, "1")


async def is_token_blacklisted(token: str) -> bool:
    """Check if token is blacklisted."""
    return await redis_client.exists(f"blacklist:{token}") > 0


# In verify_token:
async def verify_token_with_blacklist(token: str) -> dict:
    """Verify token and check blacklist."""
    if await is_token_blacklisted(token):
        raise AuthenticationError("Token has been revoked")
    return verify_token(token)
```

---

## Rate Limiting

Protect auth endpoints from abuse:

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/github")
@limiter.limit("10/minute")
async def github_callback(request: Request, ...):
    """Rate-limited GitHub OAuth callback."""
    pass

@router.post("/refresh")
@limiter.limit("30/minute")
async def refresh_token(request: Request, ...):
    """Rate-limited token refresh."""
    pass
```

---

## Environment Variables

```bash
# GitHub OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_REDIRECT_URI=http://localhost:8000/api/v1/auth/github/callback

# JWT
JWT_SECRET_KEY=your-super-secret-key-at-least-32-characters
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Redis (for token blacklist)
REDIS_URL=redis://localhost:6379/0
```

---

## Security Best Practices

1. **Strong Secret Key**: Use at least 32 random characters for JWT_SECRET_KEY
2. **HTTPS Only**: Always use HTTPS in production
3. **Short Access Tokens**: 30 minutes or less
4. **Secure Cookie Storage**: If storing tokens in cookies, use HttpOnly and Secure flags
5. **Token Rotation**: Issue new refresh token on each refresh
6. **Scope Validation**: Validate token type matches expected use
7. **Rate Limiting**: Prevent brute force attacks on auth endpoints

---

## Testing

```python
# tests/unit/test_security.py
import pytest
from agent_marketplace_api.security import (
    create_access_token,
    create_refresh_token,
    verify_token,
    AuthenticationError,
)


class TestJWT:
    """Tests for JWT token handling."""

    def test_create_and_verify_access_token(self):
        """Test access token creation and verification."""
        token = create_access_token({"sub": "123", "username": "test"})
        payload = verify_token(token, token_type="access")

        assert payload["sub"] == "123"
        assert payload["username"] == "test"
        assert payload["type"] == "access"

    def test_create_and_verify_refresh_token(self):
        """Test refresh token creation and verification."""
        token = create_refresh_token({"sub": "123", "username": "test"})
        payload = verify_token(token, token_type="refresh")

        assert payload["sub"] == "123"
        assert payload["type"] == "refresh"

    def test_verify_wrong_token_type_fails(self):
        """Test that using wrong token type raises error."""
        access_token = create_access_token({"sub": "123"})

        with pytest.raises(AuthenticationError, match="Invalid token type"):
            verify_token(access_token, token_type="refresh")

    def test_verify_expired_token_fails(self):
        """Test that expired token raises error."""
        from datetime import timedelta

        token = create_access_token(
            {"sub": "123"},
            expires_delta=timedelta(seconds=-1),  # Already expired
        )

        with pytest.raises(AuthenticationError, match="expired"):
            verify_token(token)

    def test_verify_invalid_token_fails(self):
        """Test that invalid token raises error."""
        with pytest.raises(AuthenticationError):
            verify_token("invalid.token.here")


# tests/integration/test_auth_api.py
@pytest.mark.asyncio
class TestAuthAPI:
    """Integration tests for auth endpoints."""

    async def test_github_oauth_success(self, client, mock_github):
        """Test successful GitHub OAuth flow."""
        mock_github.setup_success_responses()

        response = await client.post(
            "/api/v1/auth/github",
            json={"code": "valid_code"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "testuser"

    async def test_protected_endpoint_requires_auth(self, client):
        """Test that protected endpoint returns 401 without token."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_protected_endpoint_with_valid_token(self, client, auth_token):
        """Test protected endpoint with valid token."""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
```
