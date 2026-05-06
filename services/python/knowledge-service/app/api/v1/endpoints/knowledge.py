# ============================================================
# 知识库 API 路由层 — POST /knowledge/upload
# ============================================================

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status

from app.core.exceptions import ForbiddenError
from app.core.logging import logger
from app.core.security import get_current_user
from app.db import get_db
from app.schemas.base import CommonResponse, KnowledgeUploadResponse
from app.services.knowledge import KnowledgeService

router = APIRouter()


def _check_knowledge_manage(user: dict[str, str | list[str]]) -> None:
    """校验 knowledge:manage 权限"""
    perms = user.get("permissions", [])
    if isinstance(perms, list) and "knowledge:manage" not in perms:
        raise ForbiddenError("需要 knowledge:manage 权限才能上传文档")


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
