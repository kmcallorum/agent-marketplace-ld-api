"""User schemas for request/response validation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    """Base user schema with common fields."""

    username: str = Field(..., min_length=1, max_length=255)
    email: EmailStr


class UserCreate(UserBase):
    """Schema for creating a user."""

    github_id: int


class UserUpdate(BaseModel):
    """Schema for updating user profile."""

    bio: str | None = Field(None, max_length=1000)
    avatar_url: str | None = None


class UserResponse(UserBase):
    """Schema for user response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    github_id: int
    avatar_url: str | None = None
    bio: str | None = None
    reputation: int = 0
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class UserSummary(BaseModel):
    """Minimal user info for embedding in other responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    avatar_url: str | None = None
