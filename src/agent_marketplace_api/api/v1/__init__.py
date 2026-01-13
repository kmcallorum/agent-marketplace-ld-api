"""API v1 package."""

from fastapi import APIRouter

from agent_marketplace_api.api.v1.agents import router as agents_router
from agent_marketplace_api.api.v1.analytics import router as analytics_router
from agent_marketplace_api.api.v1.auth import router as auth_router
from agent_marketplace_api.api.v1.reviews import router as reviews_router
from agent_marketplace_api.api.v1.search import router as search_router
from agent_marketplace_api.api.v1.upload import router as upload_router
from agent_marketplace_api.api.v1.users import router as users_router
from agent_marketplace_api.api.v1.categories import router as categories_router

router = APIRouter()
router.include_router(agents_router, prefix="/agents", tags=["agents"])
router.include_router(analytics_router, tags=["analytics"])
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(reviews_router, tags=["reviews"])
router.include_router(search_router, tags=["search"])
router.include_router(upload_router, prefix="/agents", tags=["downloads"])
router.include_router(users_router, prefix="/users", tags=["users"])
router.include_router(categories_router, prefix="/categories", tags=["categories"])

__all__ = ["router"]
