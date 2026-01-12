"""Analytics API endpoints."""

from fastapi import APIRouter, Query

from agent_marketplace_api.api.deps import AnalyticsServiceDep
from agent_marketplace_api.schemas.agent import AgentSummary
from agent_marketplace_api.schemas.analytics import (
    AgentStats,
    DownloadStats,
    PlatformStatsResponse,
    PopularResponse,
    TrendingAgentItem,
    TrendingResponse,
    UserStats,
)

router = APIRouter(tags=["analytics"])


@router.get("/stats", response_model=PlatformStatsResponse)
async def get_platform_stats(
    service: AnalyticsServiceDep,
) -> PlatformStatsResponse:
    """
    Get platform-wide statistics.

    Returns counts for agents (total, validated, pending),
    users (total, active this month), and downloads (total, last 30 days).
    """
    stats = await service.get_platform_stats()

    return PlatformStatsResponse(
        agents=AgentStats(
            total=stats.agents.total,
            validated=stats.agents.validated,
            pending=stats.agents.pending,
        ),
        users=UserStats(
            total=stats.users.total,
            active_this_month=stats.users.active_this_month,
        ),
        downloads=DownloadStats(
            total=stats.downloads.total,
            last_30_days=stats.downloads.last_30_days,
        ),
    )


@router.get("/trending", response_model=TrendingResponse)
async def get_trending_agents(
    service: AnalyticsServiceDep,
    timeframe: str = Query(
        "week",
        pattern=r"^(hour|day|week|month)$",
        description="Time period for trend calculation",
    ),
    limit: int = Query(10, ge=1, le=50, description="Maximum agents to return"),
) -> TrendingResponse:
    """
    Get trending agents based on recent activity.

    Trending is calculated using downloads, stars, and recent activity.
    Timeframe options: hour, day, week (default), month.
    """
    trending = await service.get_trending_agents(timeframe=timeframe, limit=limit)

    return TrendingResponse(
        agents=[
            TrendingAgentItem(
                agent=AgentSummary.model_validate(t.agent),
                trend_score=t.trend_score,
                downloads_change=t.downloads_change,
            )
            for t in trending
        ]
    )


@router.get("/popular", response_model=PopularResponse)
async def get_popular_agents(
    service: AnalyticsServiceDep,
    limit: int = Query(10, ge=1, le=50, description="Maximum agents to return"),
) -> PopularResponse:
    """
    Get most popular agents by downloads and stars.

    Returns agents sorted by download count.
    """
    agents, total = await service.get_popular_agents(limit=limit)

    return PopularResponse(
        items=[AgentSummary.model_validate(a) for a in agents],
        total=total,
        limit=limit,
    )
