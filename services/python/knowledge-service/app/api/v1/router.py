# ============================================================
# API v1 路由聚合
# ============================================================

from fastapi import APIRouter

from app.api.v1 import health
from app.api.v1.endpoints import knowledge

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["知识库"])
