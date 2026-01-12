"""Analytics schemas for request/response validation."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from agent_marketplace_api.schemas.agent import AgentSummary


class DailyCount(BaseModel):
    """Daily count data point."""

    date: date
    count: int


class AgentStats(BaseModel):
    """Agent-related statistics."""

    total: int
    validated: int
    pending: int


class UserStats(BaseModel):
    """User-related statistics."""

    total: int
    active_this_month: int


class DownloadStats(BaseModel):
    """Download-related statistics."""

    total: int
    last_30_days: int


class PlatformStatsResponse(BaseModel):
    """Response for platform statistics."""

    agents: AgentStats
    users: UserStats
    downloads: DownloadStats


class TrendingAgentItem(BaseModel):
    """Single trending agent with trend data."""

    agent: AgentSummary
    trend_score: Decimal = Field(..., decimal_places=2)
    downloads_change: str


class TrendingResponse(BaseModel):
    """Response for trending agents."""

    agents: list[TrendingAgentItem]


class PopularResponse(BaseModel):
    """Response for popular agents."""

    items: list[AgentSummary]
    total: int
    limit: int
