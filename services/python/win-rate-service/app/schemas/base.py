# ============================================================
# Pydantic 基类 — 统一响应格式与分页
# ============================================================

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


class CommonResponse(BaseModel):
    code: int = Field(default=200, description="业务状态码")
    message: str = Field(default="success", description="消息")
    data: Any | None = Field(default=None, description="响应数据")
    request_id: str = Field(default="", description="请求唯一 ID")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int
