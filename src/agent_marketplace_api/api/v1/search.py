"""Search API endpoints."""

from fastapi import APIRouter, Query

from agent_marketplace_api.api.deps import SearchServiceDep
from agent_marketplace_api.schemas.agent import AgentSummary
from agent_marketplace_api.schemas.search import (
    AgentSearchResponse,
    GlobalSearchResponse,
    SuggestionResponse,
)
from agent_marketplace_api.schemas.user import UserSummary

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=GlobalSearchResponse)
async def global_search(
    service: SearchServiceDep,
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    type: str | None = Query(None, pattern=r"^(agents|users)$", description="Filter by type"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results per type"),
) -> GlobalSearchResponse:
    """
    Global search across agents and users.

    Searches agent names, descriptions, and slugs.
    Searches user usernames and bios.
    """
    result = await service.global_search(q, search_type=type, limit=limit)

    return GlobalSearchResponse(
        agents=[AgentSummary.model_validate(a) for a in result.agents],
        users=[UserSummary.model_validate(u) for u in result.users],
        total=result.total,
    )


@router.get("/agents", response_model=AgentSearchResponse)
async def search_agents(
    service: SearchServiceDep,
    q: str | None = Query(None, max_length=200, description="Search query (optional)"),
    category: str | None = Query(None, description="Filter by category slug"),
    min_rating: float | None = Query(None, ge=0, le=5, description="Minimum rating"),
    sort: str = Query(
        "relevance",
        pattern=r"^(relevance|downloads|stars|rating|created_at)$",
        description="Sort order",
    ),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> AgentSearchResponse:
    """
    Search agents by name and description, or browse by category.

    Supports filtering by category and minimum rating.
    Results can be sorted by relevance, downloads, stars, rating, or creation date.
    If no query is provided, returns all agents (optionally filtered by category).
    """
    result = await service.search_agents(
        q or "",
        category=category,
        min_rating=min_rating,
        sort=sort,
        limit=limit,
        offset=offset,
    )

    return AgentSearchResponse(
        items=[AgentSummary.model_validate(a) for a in result.items],
        total=result.total,
        limit=result.limit,
        offset=result.offset,
        has_more=result.has_more,
    )


@router.get("/suggestions", response_model=SuggestionResponse)
async def get_suggestions(
    service: SearchServiceDep,
    q: str = Query(..., min_length=1, max_length=200, description="Partial search query"),
) -> SuggestionResponse:
    """
    Get search suggestions based on partial query.

    Returns agent names that match the query prefix.
    """
    suggestions = await service.get_suggestions(q, limit=10)

    return SuggestionResponse(suggestions=suggestions)
