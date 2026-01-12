"""Agent schemas for request/response validation."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from agent_marketplace_api.schemas.user import UserSummary


class AgentBase(BaseModel):
    """Base agent schema with common fields."""

    name: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=10)


class AgentCreate(AgentBase):
    """Schema for creating an agent."""

    category: str = Field(..., min_length=1, max_length=100)
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")


class AgentUpdate(BaseModel):
    """Schema for updating agent metadata."""

    name: str | None = Field(None, min_length=3, max_length=255)
    description: str | None = Field(None, min_length=10)
    category: str | None = Field(None, min_length=1, max_length=100)
    is_public: bool | None = None


class AgentVersionCreate(BaseModel):
    """Schema for publishing a new version."""

    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    changelog: str | None = Field(None, max_length=5000)


class AgentVersionResponse(BaseModel):
    """Schema for agent version response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    changelog: str | None = None
    size_bytes: int | None = None
    tested: bool = False
    security_scan_passed: bool = False
    quality_score: Decimal | None = None
    published_at: datetime


class AgentResponse(AgentBase):
    """Schema for agent response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    author: UserSummary
    current_version: str
    downloads: int = 0
    stars: int = 0
    rating: Decimal = Decimal("0.00")
    is_public: bool = True
    is_validated: bool = False
    created_at: datetime
    updated_at: datetime
    versions: list[AgentVersionResponse] = []


class AgentSummary(BaseModel):
    """Minimal agent info for list responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str
    author: UserSummary
    current_version: str
    downloads: int = 0
    stars: int = 0
    rating: Decimal = Decimal("0.00")
    is_validated: bool = False
    created_at: datetime


class AgentListResponse(BaseModel):
    """Schema for paginated agent list response."""

    items: list[AgentSummary]
    total: int
    limit: int
    offset: int
    has_more: bool = False
