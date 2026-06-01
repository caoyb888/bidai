# ============================================================
# 知识库 API 路由层 — POST /knowledge/upload
# ============================================================

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status

from app.core.exceptions import ForbiddenError
from app.core.logging import logger
from app.core.security import get_current_user
from app.db import get_db
from app.schemas.base import (
    CommonResponse,
    KnowledgeDocument,
    KnowledgeDocumentListResponse,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    KnowledgeStatsResponse,
    KnowledgeUploadResponse,
    PaginationParams,
)
from app.services.knowledge import KnowledgeService

router = APIRouter()


def _check_bid_edit(user: dict[str, str | list[str]]) -> None:
    """校验 bid:edit 权限"""
    perms = user.get("permissions", [])
    if isinstance(perms, list) and "bid:edit" not in perms:
        raise ForbiddenError("需要 bid:edit 权限")


def _check_knowledge_manage(user: dict[str, str | list[str]]) -> None:
    """校验 knowledge:manage 权限"""
    perms = user.get("permissions", [])
    if isinstance(perms, list) and "knowledge:manage" not in perms:
        raise ForbiddenError("需要 knowledge:manage 权限")


@router.post(
    "/upload",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CommonResponse[KnowledgeUploadResponse],
    summary="上传文档入库",
    description="上传文档至企业知识库，支持 pdf/docx/xlsx/jpg/png，单文件不超过 100MB，自动 SHA-256 去重",
)
async def upload_document(
    request: Request,
    file: Annotated[UploadFile, File(description="上传文件")],
    doc_category: Annotated[
        str,
        Form(description="文档分类"),
    ],
    title: Annotated[str | None, Form(description="文档标题，不填则使用原始文件名")] = None,
    tags: Annotated[str | None, Form(description='标签列表（JSON 数组字符串），如 ["政务信息化","广东省"]')] = None,
    current_user: dict[str, str | list[str]] = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> CommonResponse[KnowledgeUploadResponse]:
    """上传文档入库接口"""
    _check_knowledge_manage(current_user)

    user_id = str(current_user.get("user_id", "unknown"))
    request_id = getattr(request.state, "request_id", "")

    # 解析 tags JSON
    parsed_tags: list[str] = []
    if tags:
        import json

        try:
            parsed_tags = json.loads(tags)
            if not isinstance(parsed_tags, list):
                parsed_tags = []
        except json.JSONDecodeError:
            parsed_tags = []

    service = KnowledgeService(db)

    result = await service.upload_document(
        file_data=file.file,
        file_name=file.filename or "unknown",
        mime_type=file.content_type or "application/octet-stream",
        doc_category=doc_category,
        title=title,
        tags=parsed_tags,
        user_id=user_id,
    )

    logger.info(
        "Knowledge upload endpoint completed",
        extra={
            "user_id": user_id,
            "document_id": result.document_id,
            "is_duplicate": result.is_duplicate,
            "request_id": request_id,
        },
    )

    return CommonResponse(
        code=202,
        message="任务已提交，请轮询状态" if not result.is_duplicate else "文件已存在",
        data=result,
        request_id=request_id,
    )


@router.get(
    "/search",
    response_model=CommonResponse[KnowledgeSearchResponse],
    summary="语义检索知识库",
    description="使用向量检索 + 全文检索混合模式，结果经 Cross-Encoder 重排序后返回",
)
async def search_knowledge(
    request: Request,
    query: Annotated[str, Query(min_length=2, description="查询关键词或自然语言描述")],
    doc_category: Annotated[str | None, Query(description="限定知识库分类")] = None,
    tags: Annotated[list[str] | None, Query(description="标签过滤")] = None,
    top_k: Annotated[int, Query(ge=1, le=50, description="返回结果数量")] = 10,
    current_user: dict[str, str | list[str]] = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> CommonResponse[KnowledgeSearchResponse]:
    """语义检索知识库接口"""
    request_id = getattr(request.state, "request_id", "")
    user_id = str(current_user.get("user_id", "unknown"))

    search_request = KnowledgeSearchRequest(
        query=query,
        doc_category=doc_category,
        tags=tags or [],
        top_k=top_k,
    )

    service = KnowledgeService(db)
    result = await service.search_knowledge(search_request)

    logger.info(
        "Knowledge search completed",
        extra={
            "user_id": user_id,
            "query": query,
            "total_found": result.total_found,
            "request_id": request_id,
        },
    )

    return CommonResponse(
        code=200,
        message="success",
        data=result,
        request_id=request_id,
    )


@router.get(
    "/documents",
    response_model=CommonResponse[KnowledgeDocumentListResponse],
    summary="获取知识库文档列表",
    description="分页获取知识库文档列表，支持按分类、标签、过期状态、关键词筛选",
)
async def list_documents(
    request: Request,
    pagination: Annotated[PaginationParams, Depends()],
    doc_category: Annotated[str | None, Query(description="文档分类筛选")] = None,
    tags: Annotated[list[str] | None, Query(description="标签筛选（含任一即匹配）")] = None,
    is_expired: Annotated[bool | None, Query(description="是否已过期")] = None,
    keyword: Annotated[str | None, Query(description="标题关键词模糊搜索")] = None,
    current_user: dict[str, str | list[str]] = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> CommonResponse[KnowledgeDocumentListResponse]:
    """知识库文档列表接口"""
    _check_bid_edit(current_user)

    request_id = getattr(request.state, "request_id", "")
    user_id = str(current_user.get("user_id", "unknown"))

    service = KnowledgeService(db)
    result = await service.list_documents(
        page=pagination.page,
        page_size=pagination.page_size,
        doc_category=doc_category,
        tags=tags,
        is_expired=is_expired,
        keyword=keyword,
    )

    logger.info(
        "Knowledge document list queried",
        extra={
            "user_id": user_id,
            "page": pagination.page,
            "page_size": pagination.page_size,
            "total": result.total,
            "request_id": request_id,
        },
    )

    return CommonResponse(
        code=200,
        message="success",
        data=result,
        request_id=request_id,
    )


@router.get(
    "/documents/{doc_id}",
    response_model=CommonResponse[KnowledgeDocument],
    summary="获取知识库文档详情",
    description="获取指定知识库文档的详细信息，已软删除的文档返回 404",
)
async def get_document(
    request: Request,
    doc_id: str,
    current_user: dict[str, str | list[str]] = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> CommonResponse[KnowledgeDocument]:
    """知识库文档详情接口"""
    _check_bid_edit(current_user)

    request_id = getattr(request.state, "request_id", "")
    user_id = str(current_user.get("user_id", "unknown"))

    service = KnowledgeService(db)
    result = await service.get_document(doc_id)

    logger.info(
        "Knowledge document detail queried",
        extra={"user_id": user_id, "doc_id": doc_id, "request_id": request_id},
    )

    return CommonResponse(
        code=200,
        message="success",
        data=result,
        request_id=request_id,
    )


@router.delete(
    "/documents/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除知识库文档（软删除）",
    description="需要 knowledge:manage 权限。删除后同步清理 Milvus 向量及 ES 索引",
)
async def delete_document(
    request: Request,
    doc_id: str,
    current_user: dict[str, str | list[str]] = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> None:
    """删除知识库文档接口"""
    _check_knowledge_manage(current_user)

    request_id = getattr(request.state, "request_id", "")
    user_id = str(current_user.get("user_id", "unknown"))

    service = KnowledgeService(db)
    await service.delete_document(doc_id, user_id)

    logger.info(
        "Knowledge document deleted",
        extra={"user_id": user_id, "doc_id": doc_id, "request_id": request_id},
    )


@router.get(
    "/stats",
    response_model=CommonResponse[KnowledgeStatsResponse],
    summary="获取知识库统计信息",
    description="返回各分类文档数量、健康度评分、过期证书预警等聚合统计",
)
async def get_knowledge_stats(
    request: Request,
    current_user: dict[str, str | list[str]] = Depends(get_current_user),
    db: Any = Depends(get_db),
) -> CommonResponse[KnowledgeStatsResponse]:
    """知识库统计信息接口"""
    _check_bid_edit(current_user)

    request_id = getattr(request.state, "request_id", "")
    user_id = str(current_user.get("user_id", "unknown"))

    service = KnowledgeService(db)
    result = await service.get_stats()

    logger.info(
        "Knowledge stats queried",
        extra={
            "user_id": user_id,
            "total_documents": result.total_documents,
            "health_score": result.health_score,
            "request_id": request_id,
        },
    )

    return CommonResponse(
        code=200,
        message="success",
        data=result,
        request_id=request_id,
    )
