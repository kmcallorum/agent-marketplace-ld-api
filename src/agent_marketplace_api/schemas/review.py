"""Review schemas for request/response validation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from agent_marketplace_api.schemas.user import UserSummary


class ReviewBase(BaseModel):
    """Base review schema with common fields."""

    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(None, max_length=5000)


class ReviewCreate(ReviewBase):
    """Schema for creating a review."""

    pass


class ReviewUpdate(BaseModel):
    """Schema for updating a review."""

    rating: int | None = Field(None, ge=1, le=5)
    comment: str | None = Field(None, max_length=5000)


class ReviewResponse(ReviewBase):
    """Schema for review response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    agent_id: int
    user: UserSummary
    helpful_count: int = 0
    created_at: datetime
    updated_at: datetime


class ReviewListResponse(BaseModel):
    """Schema for paginated review list response."""

    items: list[ReviewResponse]
    total: int
    average_rating: float = 0.0
