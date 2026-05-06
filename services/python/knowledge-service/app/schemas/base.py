# ============================================================
# Pydantic 基类 — 统一响应格式与分页
# ============================================================

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class CommonResponse(BaseModel, Generic[T]):
    code: int = Field(default=200, description="业务状态码")
    message: str = Field(default="success", description="消息")
    data: T | None = Field(default=None, description="响应数据")
    request_id: str = Field(default="", description="请求唯一 ID")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


class AsyncTaskResponse(BaseModel):
    task_id: str = Field(description="任务唯一 ID")
    status: str = Field(default="PENDING", description="任务状态")
    poll_url: str = Field(description="轮询地址")
    estimated_seconds: int = Field(default=30, description="预计完成时间（秒）")


class KnowledgeUploadResponse(AsyncTaskResponse):
    document_id: str = Field(description="文档 ID")
    is_duplicate: bool = Field(default=False, description="是否为重复文件")
