# ============================================================
# FastAPI 应用入口
# ============================================================

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exception_handlers import base_service_exception_handler
from app.core.exceptions import BaseServiceException
from app.core.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(f"{settings.app_name} starting up", extra={"env": settings.app_env})
    yield
    logger.info(f"{settings.app_name} shutting down")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="AI 智能投标系统 · Python 微服务",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(BaseServiceException, base_service_exception_handler)  # type: ignore[arg-type]

app.include_router(api_router, prefix="/api/v1")
