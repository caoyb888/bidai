# ============================================================
# Pydantic 基类 — 统一响应格式与分页
# ============================================================

from typing import Generic, Literal, TypeVar

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


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=2, description="查询关键词或自然语言描述")
    doc_category: str | None = Field(default=None, description="限定知识库分类")
    tags: list[str] = Field(default_factory=list, description="标签过滤")
    top_k: int = Field(default=10, ge=1, le=50, description="返回结果数量")


class KnowledgeSearchResult(BaseModel):
    chunk_id: str = Field(description="分块 ID")
    doc_id: str = Field(description="文档 ID")
    doc_title: str = Field(description="文档标题")
    content: str = Field(description="匹配的文本分块内容")
    page_no: int | None = Field(default=None, description="所在页码")
    score: float = Field(description="相关度分数 0~1")
    highlight: str = Field(default="", description="高亮片段（含 HTML 标签）")


class KnowledgeSearchResponse(BaseModel):
    results: list[KnowledgeSearchResult]
    total_found: int = Field(description="结果总数")


class KnowledgeDocument(BaseModel):
    id: str = Field(description="文档 ID")
    title: str = Field(description="文档标题")
    doc_category: Literal[
        "QUALIFICATION", "PERFORMANCE", "PERSONNEL", "SOLUTION_TEMPLATE", "GENERAL"
    ] = Field(description="文档分类")
    tags: list[str] = Field(default_factory=list, description="标签列表")
    file_type: str = Field(description="文件类型，如 pdf/docx")
    page_count: int | None = Field(default=None, description="页数")
    confidence: float = Field(default=0.0, description="AI 分类置信度")
    ingest_mode: Literal["AUTO", "MANUAL_CONFIRM", "MANUAL"] = Field(
        default="AUTO", description="入库方式"
    )
    is_expired: bool = Field(default=False, description="是否已过期")
    created_at: str = Field(description="创建时间 ISO 8601")


class KnowledgeDocumentListResponse(BaseModel):
    items: list[KnowledgeDocument]
    total: int
    page: int
    page_size: int
    total_pages: int


class CategoryStat(BaseModel):
    category: Literal[
        "QUALIFICATION", "PERFORMANCE", "PERSONNEL", "SOLUTION_TEMPLATE", "GENERAL"
    ] = Field(description="文档分类")
    count: int = Field(description="该分类文档总数")
    expired_count: int = Field(description="该分类已过期文档数")


class ExpiringSoonItem(BaseModel):
    doc_id: str = Field(description="文档 ID")
    title: str = Field(description="文档标题")
    expire_date: str = Field(description="过期日期（ISO 8601 日期格式）")


class KnowledgeStatsResponse(BaseModel):
    total_documents: int = Field(description="知识库文档总数（不含软删除）")
    health_score: float = Field(description="知识库健康度评分 0~100，≥70 可正常运行")
    category_stats: list[CategoryStat] = Field(description="各分类文档统计")
    expiring_soon: list[ExpiringSoonItem] = Field(description="即将过期的文档（30天内）")
