"""Search schemas for request/response validation."""

from pydantic import BaseModel, Field

from agent_marketplace_api.schemas.agent import AgentSummary
from agent_marketplace_api.schemas.user import UserSummary


class SearchParams(BaseModel):
    """Parameters for global search."""

    q: str = Field(..., min_length=1, max_length=200)
    type: str | None = Field(None, pattern=r"^(agents|users)$")
    limit: int = Field(20, ge=1, le=100)


class AgentSearchParams(BaseModel):
    """Parameters for agent-specific search."""

    q: str = Field(..., min_length=1, max_length=200)
    category: str | None = None
    min_rating: float | None = Field(None, ge=0, le=5)
    sort: str = Field("relevance", pattern=r"^(relevance|downloads|stars|rating|created_at)$")
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class SuggestionParams(BaseModel):
    """Parameters for search suggestions."""

    q: str = Field(..., min_length=1, max_length=200)


class GlobalSearchResponse(BaseModel):
    """Response for global search."""

    agents: list[AgentSummary]
    users: list[UserSummary]
    total: int


class AgentSearchResponse(BaseModel):
    """Response for agent search."""

    items: list[AgentSummary]
    total: int
    limit: int
    offset: int
    has_more: bool = False


class SuggestionResponse(BaseModel):
    """Response for search suggestions."""

    suggestions: list[str]
