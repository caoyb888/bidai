# ============================================================
# ES 索引同步封装 — 文档 → Elasticsearch 全文索引
# 职责：将向量化后的文档 chunks 批量写入 ES，更新同步状态
# 被调用方：vectorize_tasks（入库时自动索引）、sync_tasks（定时补偿）
# ============================================================

from __future__ import annotations

from app.ai.es_client import ESClient, ESError
from app.core.logging import logger
from app.db import AsyncSessionLocal
from app.repositories.kb_chunk import KbChunkRepository
from app.repositories.knowledge import KnowledgeRepository


async def sync_document_to_es(doc_id: str) -> bool:
    """
    将文档的所有 chunks 同步到 Elasticsearch。

    流程：
    1. 查询 kb_documents 确认文档存在且未软删除
    2. 查询 kb_chunks 获取全部分块
    3. 调用 ESClient 批量索引（自动创建索引）
    4. 更新 kb_documents.es_indexed = True

    Args:
        doc_id: 文档 ID（字符串 UUID）

    Returns:
        同步是否成功
    """
    async with AsyncSessionLocal() as session:
        kb_repo = KnowledgeRepository(session)
        chunk_repo = KbChunkRepository(session)

        # 1. 查询文档
        doc = await kb_repo.get_by_id(doc_id)
        if doc is None:
            logger.warning(
                "ES sync skipped: document not found",
                extra={"doc_id": doc_id},
            )
            return False

        if doc.deleted_at is not None:
            logger.warning(
                "ES sync skipped: document already soft-deleted",
                extra={"doc_id": doc_id},
            )
            return False

        # 2. 查询分块
        chunks = await chunk_repo.get_by_doc_id(doc_id)
        if not chunks:
            logger.warning(
                "ES sync skipped: no chunks found for document",
                extra={"doc_id": doc_id},
            )
            return False

        # 3. 构建 ES 文档并批量索引
        es_client = ESClient()
        es_docs: list[dict[str, object]] = []
        for chunk in chunks:
            es_docs.append(
                {
                    "chunk_id": str(chunk.id),
                    "doc_id": doc_id,
                    "content": chunk.content,
                    "chunk_type": chunk.chunk_type,
                    "page_no": chunk.page_no,
                    "section_title": chunk.section_title or "",
                    "doc_title": doc.title,
                    "tags": list(doc.tags) if doc.tags else [],
                }
            )

        try:
            await es_client.ensure_index()
            await es_client.bulk_index_chunks(es_docs)
        except ESError as exc:
            logger.warning(
                "ES sync failed during bulk index",
                extra={
                    "doc_id": doc_id,
                    "chunks": len(es_docs),
                    "error": str(exc),
                },
            )
            return False

        # 4. 更新文档 ES 同步状态并提交事务
        await kb_repo.update_es_index_status(doc_id, es_indexed=True)
        await session.commit()

        logger.info(
            "ES sync completed successfully",
            extra={"doc_id": doc_id, "indexed_chunks": len(es_docs)},
        )
        return True
