# ============================================================
# Celery AI 任务 — 文档 OCR 解析
# ============================================================

import asyncio
import tempfile
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from celery import states
from celery.exceptions import MaxRetriesExceededError

from app.ai.parsers.factory import get_parser
from app.core.logging import logger
from app.db import AsyncSessionLocal
from app.repositories.ai_task import AiTaskRepository
from app.repositories.knowledge import KnowledgeRepository
from app.utils.minio_client import MinioClient
from app.worker import celery_app


async def _mark_task_failed(doc_id: str, error_message: str) -> None:
    """将文档和关联任务标记为失败"""
    async with AsyncSessionLocal() as session:
        kb_repo = KnowledgeRepository(session)
        task_repo = AiTaskRepository(session)

        await kb_repo.update_parse_status(
            doc_id,
            parse_status="FAILED",
            parse_error=error_message,
        )

        task = await task_repo.get_by_ref("KB_DOCUMENT", doc_id)
        if task is not None:
            await task_repo.update_status(
                cast(UUID, task.id),
                task_status="FAILED",
                error_message=error_message,
            )

        await session.commit()


async def _process_document(doc_id: str, celery_task_id: str) -> dict[str, Any]:
    """异步执行文档 OCR 解析"""
    minio = MinioClient()

    async with AsyncSessionLocal() as session:
        kb_repo = KnowledgeRepository(session)
        task_repo = AiTaskRepository(session)

        # 1. 查询文档信息
        doc = await kb_repo.get_by_id(doc_id)
        if doc is None:
            raise ValueError(f"Document not found: {doc_id}")

        # 2. 更新关联任务为 RUNNING
        task = await task_repo.get_by_ref("KB_DOCUMENT", doc_id)
        if task is not None:
            await task_repo.update_status(cast(UUID, task.id), task_status="RUNNING")
            # 记录 Celery task_id（可能和之前不同，如果是重试）
            task.celery_task_id = celery_task_id  # type: ignore[assignment]

        await session.commit()

        # 3. 下载原始文件到临时目录
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = Path(tmpdir) / doc.file_name
            minio.download_file(doc.file_path, str(local_path))  # type: ignore[arg-type]

            # 4. 根据 mime_type 选择解析器执行 OCR
            parser = get_parser(doc.mime_type)  # type: ignore[arg-type]
            parse_result = parser.parse(str(local_path))

            # 5. 解析文本上传 MinIO
            # 路径约定: {year}/{month}/{doc_id}/{doc_id}_parsed.txt
            parsed_object_path = doc.file_path.rsplit(".", 1)[0] + "_parsed.txt"
            minio.upload_text(parse_result.text, parsed_object_path)

            # 6. 更新 kb_documents 状态
            await kb_repo.update_parse_status(
                doc_id,
                parse_status="SUCCESS",
                page_count=parse_result.page_count,
                word_count=parse_result.word_count,
                parsed_text_path=parsed_object_path,
            )

            # 7. 更新 ai_tasks 状态为 SUCCESS
            if task is not None:
                await task_repo.update_status(
                    cast(UUID, task.id),
                    task_status="SUCCESS",
                    result_payload={
                        "doc_id": doc_id,
                        "page_count": parse_result.page_count,
                        "word_count": parse_result.word_count,
                        "is_scanned": parse_result.is_scanned,
                        "parsed_text_path": parsed_object_path,
                    },
                )

        await session.commit()

        logger.info(
            "Document OCR parsing completed",
            extra={
                "doc_id": doc_id,
                "celery_task_id": celery_task_id,
                "page_count": parse_result.page_count,
                "word_count": parse_result.word_count,
                "is_scanned": parse_result.is_scanned,
            },
        )

        return {
            "doc_id": doc_id,
            "status": "SUCCESS",
            "page_count": parse_result.page_count,
            "word_count": parse_result.word_count,
            "is_scanned": parse_result.is_scanned,
            "parsed_text_path": parsed_object_path,
        }


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    soft_time_limit=300,
    time_limit=600,
)
def process_document_task(self: Any, doc_id: str) -> dict[str, str]:
    """
    文档 OCR 解析 Celery 任务

    流程：
    1. 查询 kb_documents 获取文件信息
    2. 更新 ai_tasks 状态为 RUNNING
    3. 从 MinIO 下载原始文件
    4. 根据 mime_type 选择解析器（PDF/DOCX/图片）
    5. 解析文本上传 MinIO
    6. 更新 kb_documents 和 ai_tasks 状态为 SUCCESS

    失败时自动重试 3 次，最终失败更新状态为 FAILED。
    """
    logger.info(
        "Document OCR task started",
        extra={"doc_id": doc_id, "celery_task_id": self.request.id},
    )

    try:
        result = asyncio.run(_process_document(doc_id, self.request.id))
        return result

    except Exception as exc:
        error_msg = str(exc)
        logger.error(
            "Document OCR task failed",
            extra={"doc_id": doc_id, "error": error_msg},
            exc_info=True,
        )

        # 更新数据库状态为 FAILED
        try:
            asyncio.run(_mark_task_failed(doc_id, error_msg))
        except Exception as mark_exc:
            logger.critical(
                "Failed to mark task as failed in database",
                extra={"doc_id": doc_id, "error": str(mark_exc)},
                exc_info=True,
            )

        # Celery 重试
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "Document OCR task max retries exceeded",
                extra={"doc_id": doc_id, "error": error_msg},
            )
            self.update_state(state=states.FAILURE, meta={"error": error_msg})
            raise
