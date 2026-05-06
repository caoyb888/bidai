# ============================================================
# 知识库业务逻辑层 — Service
# ============================================================

from typing import BinaryIO
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tasks import process_document_task
from app.core.config import settings
from app.core.exceptions import (
    FileTooLargeError,
    InvalidFileTypeError,
    StorageError,
)
from app.core.logging import logger
from app.models.kb_document import KbDocument
from app.repositories.ai_task import AiTaskRepository
from app.repositories.knowledge import KnowledgeRepository
from app.schemas.base import KnowledgeUploadResponse
from app.utils.minio_client import MinioClient, compute_sha256, get_file_extension


class KnowledgeService:
    """知识库业务服务"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.kb_repo = KnowledgeRepository(session)
        self.task_repo = AiTaskRepository(session)
        self.minio = MinioClient()

    @staticmethod
    def _map_doc_category(doc_category: str) -> str:
        """将 API 的 doc_category 映射到数据库 document_type 枚举值"""
        mapping = {
            "QUALIFICATION": "QUALIFICATION",
            "PERFORMANCE": "PERFORMANCE",
            "PERSONNEL": "PERSONNEL",
            "SOLUTION_TEMPLATE": "SOLUTION",
            "GENERAL": "MISC",
        }
        return mapping.get(doc_category, "MISC")

    async def upload_document(
        self,
        file_data: BinaryIO,
        file_name: str,
        mime_type: str,
        doc_category: str,
        title: str | None,
        tags: list[str],
        user_id: str,
    ) -> KnowledgeUploadResponse:
        """
        上传文档入库

        流程：类型校验 → 大小校验 → 计算 SHA-256 → 查重 → 存 MinIO → 写 DB → 发 Celery 任务
        """
        # 映射 doc_category 到数据库枚举值
        db_doc_type = self._map_doc_category(doc_category)
        # 1. 文件类型白名单校验
        ext = get_file_extension(file_name)
        if ext not in settings.upload_allowed_extensions:
            logger.warning(
                "Invalid file type uploaded",
                extra={"file_name": file_name, "extension": ext, "user_id": user_id},
            )
            raise InvalidFileTypeError(ext)

        # 2. 文件大小限制校验
        file_data.seek(0, 2)  # seek to end
        file_size = file_data.tell()
        file_data.seek(0)
        size_mb = file_size / (1024 * 1024)
        if size_mb > settings.upload_max_size_mb:
            logger.warning(
                "File too large",
                extra={
                    "file_name": file_name,
                    "size_mb": round(size_mb, 2),
                    "max_mb": settings.upload_max_size_mb,
                    "user_id": user_id,
                },
            )
            raise FileTooLargeError(size_mb, settings.upload_max_size_mb)

        # 3. 计算 SHA-256
        file_hash = compute_sha256(file_data)

        # 4. 哈希去重检查
        existing = await self.kb_repo.get_by_file_hash(file_hash)
        if existing is not None:
            logger.info(
                "Duplicate file detected",
                extra={
                    "file_hash": file_hash,
                    "existing_doc_id": str(existing.id),
                    "user_id": user_id,
                },
            )
            return KnowledgeUploadResponse(
                task_id="",
                status="SUCCESS",
                poll_url="",
                estimated_seconds=0,
                document_id=str(existing.id),
                is_duplicate=True,
            )

        # 5. 生成文档 ID 并上传 MinIO
        doc_id = uuid4()
        doc_title = title if title else file_name

        try:
            file_path = self.minio.upload_file(
                file_data=file_data,
                file_name=file_name,
                mime_type=mime_type,
                doc_id=str(doc_id),
            )
        except StorageError:
            raise
        except Exception as exc:
            logger.error(
                "MinIO upload failed",
                extra={"doc_id": str(doc_id), "file_name": file_name},
                exc_info=True,
            )
            raise StorageError("文件上传失败") from exc

        # 6. 写入 kb_documents 记录
        doc = KbDocument(
            id=doc_id,
            doc_type=db_doc_type,
            title=doc_title,
            file_path=file_path,
            file_name=file_name,
            file_size_bytes=file_size,
            mime_type=mime_type,
            file_hash=file_hash,
            parse_status="PENDING",
            tags=tags if tags else [],
            created_by=user_id,
            updated_by=user_id,
        )
        await self.kb_repo.create(doc)

        # 7. 提交 Celery 异步任务（占位）
        celery_task = process_document_task.delay(str(doc_id))

        # 8. 写入 ai_tasks 记录
        task = await self.task_repo.create(
            task_type="DOC_PARSE",
            ref_type="KB_DOCUMENT",
            ref_id=doc_id,
            celery_task_id=celery_task.id,
            input_payload={"doc_id": str(doc_id), "file_path": file_path},
            created_by=user_id,
        )

        await self.session.commit()

        logger.info(
            "Document uploaded successfully",
            extra={
                "doc_id": str(doc_id),
                "task_id": str(task.id),
                "celery_task_id": celery_task.id,
                "user_id": user_id,
                "file_size_bytes": file_size,
            },
        )

        return KnowledgeUploadResponse(
            task_id=str(task.id),
            status="PENDING",
            poll_url=f"/api/v1/tasks/{task.id}",
            estimated_seconds=30,
            document_id=str(doc_id),
            is_duplicate=False,
        )
