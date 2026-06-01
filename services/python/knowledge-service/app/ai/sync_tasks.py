# ============================================================
# Celery 定时同步任务 — ES 索引补偿
# 每 5 分钟扫描一次 es_indexed=False 的文档，触发补偿索引
# ============================================================

from __future__ import annotations

import asyncio
from typing import Any

from celery import states
from celery.exceptions import MaxRetriesExceededError

from app.ai.es_indexer import sync_document_to_es
from app.core.logging import logger
from app.db import AsyncSessionLocal
from app.repositories.knowledge import KnowledgeRepository
from app.worker import celery_app


async def _compensate_es_index() -> dict[str, Any]:
    """扫描并补偿未同步 ES 的文档"""
    async with AsyncSessionLocal() as session:
        kb_repo = KnowledgeRepository(session)
        docs = await kb_repo.get_unindexed_documents(limit=50)

        if not docs:
            return {"compensated": 0, "failed": 0, "doc_ids": []}

        compensated = 0
        failed = 0
        doc_ids: list[str] = []

        for doc in docs:
            doc_id = str(doc.id)
            success = await sync_document_to_es(doc_id)
            if success:
                compensated += 1
                doc_ids.append(doc_id)
            else:
                failed += 1

        return {
            "compensated": compensated,
            "failed": failed,
            "doc_ids": doc_ids,
        }


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=120,
    time_limit=300,
)
def es_index_compensate_task(self: Any) -> dict[str, Any]:
    """
    ES 索引补偿任务 — 每 5 分钟执行一次（通过 Celery Beat 调度）。

    扫描 es_indexed=False 且 parse_status=SUCCESS 且未软删除的文档，
    调用 sync_document_to_es 进行补偿索引。
    """
    logger.info(
        "ES index compensate task started",
        extra={"celery_task_id": self.request.id},
    )

    try:
        result = asyncio.run(_compensate_es_index())

        logger.info(
            "ES index compensate task completed",
            extra={
                "compensated": result["compensated"],
                "failed": result["failed"],
                "doc_ids": result["doc_ids"],
            },
        )
        return result

    except Exception as exc:
        error_msg = str(exc)
        logger.error(
            "ES index compensate task failed",
            extra={"error": error_msg},
            exc_info=True,
        )

        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "ES index compensate task max retries exceeded",
                extra={"error": error_msg},
            )
            self.update_state(state=states.FAILURE, meta={"error": error_msg})
            raise
