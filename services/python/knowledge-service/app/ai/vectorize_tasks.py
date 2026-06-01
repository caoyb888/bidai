# ============================================================
# Celery AI 任务 — 文档分块与向量化
# 写入 Milvus + PostgreSQL
# ============================================================

import asyncio
import hashlib
import json
from typing import Any, cast
from uuid import UUID, uuid4

from celery import states
from celery.exceptions import MaxRetriesExceededError

from app.ai.chunker import DocumentChunker
from app.ai.embedding import EmbeddingClient, EmbeddingError
from app.ai.es_indexer import sync_document_to_es
from app.ai.milvus_client import MilvusClient, MilvusError
from app.ai.parsers.base import DocumentFragment
from app.core.config import settings
from app.core.logging import logger
from app.db import AsyncSessionLocal
from app.models.kb_chunk import KbChunk
from app.repositories.ai_task import AiTaskRepository
from app.repositories.kb_chunk import KbChunkRepository
from app.repositories.knowledge import KnowledgeRepository
from app.utils.minio_client import MinioClient
from app.worker import celery_app


async def _mark_vectorize_task_failed(
    doc_id: str,
    task_id: str,
    error_message: str,
) -> None:
    """将向量化任务标记为失败"""
    async with AsyncSessionLocal() as session:
        task_repo = AiTaskRepository(session)
        task = await task_repo.get_by_ref("KB_DOCUMENT", doc_id)
        if task is not None:
            await task_repo.update_status(
                cast(UUID, task.id),
                task_status="FAILED",
                error_message=error_message,
            )
        await session.commit()


async def _vectorize_document(
    doc_id: str,
    celery_task_id: str,
) -> dict[str, Any]:
    """异步执行文档分块与向量化"""
    minio = MinioClient()
    chunker = DocumentChunker()
    embed_client = EmbeddingClient()
    milvus_client = MilvusClient()

    async with AsyncSessionLocal() as session:
        kb_repo = KnowledgeRepository(session)
        chunk_repo = KbChunkRepository(session)
        task_repo = AiTaskRepository(session)

        # 1. 查询文档信息
        doc = await kb_repo.get_by_id(doc_id)
        if doc is None:
            raise ValueError(f"Document not found: {doc_id}")

        if doc.parse_status != "SUCCESS":
            raise ValueError(f"Document not parsed yet: {doc_id}, status={doc.parse_status}")

        # 2. 更新关联任务为 RUNNING
        task = await task_repo.get_by_ref("KB_DOCUMENT", doc_id)
        if task is not None:
            await task_repo.update_status(cast(UUID, task.id), task_status="RUNNING")
            task.celery_task_id = celery_task_id  # type: ignore[assignment]
        await session.commit()

        # 3. 从 MinIO 下载结构化片段 JSON
        fragments_path = doc.file_path.rsplit(".", 1)[0] + "_fragments.json"
        try:
            fragments_json = minio.download_text(fragments_path)
            fragments_raw = json.loads(fragments_json)
            fragments = [
                DocumentFragment(
                    content=f["content"],
                    page_no=f.get("page_no", 0),
                    fragment_type=f.get("fragment_type", "TEXT"),
                    section_title=f.get("section_title", ""),
                )
                for f in fragments_raw
            ]
        except Exception as exc:
            logger.warning(
                "Failed to load fragments JSON, falling back to parsed text",
                extra={"doc_id": doc_id, "fragments_path": fragments_path, "error": str(exc)},
            )
            # 兜底：从解析文本重建单个 TEXT fragment
            parsed_text_path = doc.file_path.rsplit(".", 1)[0] + "_parsed.txt"
            try:
                parsed_text = minio.download_text(parsed_text_path)
                fragments = [DocumentFragment(content=parsed_text, page_no=0, fragment_type="TEXT")]
            except Exception as text_exc:
                raise ValueError(f"Cannot load parsed content for doc {doc_id}: {text_exc}") from text_exc

        # 4. 分块
        chunks = chunker.chunk_fragments(fragments)
        if not chunks:
            raise ValueError(f"No chunks generated for doc {doc_id}")

        # 验证 token 约束
        for chunk in chunks:
            if chunk.token_count > settings.chunk_max_tokens:
                logger.warning(
                    "Chunk exceeds max token limit",
                    extra={
                        "doc_id": doc_id,
                        "chunk_type": chunk.chunk_type,
                        "token_count": chunk.token_count,
                        "max_tokens": settings.chunk_max_tokens,
                    },
                )

        # 5. 批量 Embedding
        chunk_texts = [c.content for c in chunks]
        try:
            embeddings = await embed_client.embed(chunk_texts)
        except EmbeddingError as exc:
            raise RuntimeError(f"Embedding failed for doc {doc_id}: {exc}") from exc

        if len(embeddings) != len(chunks):
            raise RuntimeError(
                f"Embedding count mismatch: {len(embeddings)} != {len(chunks)}"
            )

        # 6. 写入 PostgreSQL kb_chunks
        # 先清理旧分块（如果存在）
        await chunk_repo.delete_by_doc_id(doc_id)

        kb_chunks: list[KbChunk] = []
        for i, chunk in enumerate(chunks):
            chunk_id = uuid4()
            content_hash = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
            kb_chunk = KbChunk(
                id=chunk_id,
                doc_id=UUID(doc_id),
                content=chunk.content,
                content_hash=content_hash,
                chunk_index=i,
                page_no=chunk.page_no,
                token_count=chunk.token_count,
                char_count=chunk.char_count,
                chunk_type=chunk.chunk_type,
                milvus_id=None,
                embedding_model=settings.embedding_model,
                embedded_at=None,
            )
            kb_chunks.append(kb_chunk)

        await chunk_repo.create_many(kb_chunks)

        # 7. 写入 Milvus
        milvus_ids = [str(c.id) for c in kb_chunks]
        doc_ids = [doc_id] * len(kb_chunks)
        chunk_ids = [str(c.id) for c in kb_chunks]
        chunk_types: list[str] = [str(c.chunk_type) for c in kb_chunks]

        try:
            milvus_client.insert_chunks(
                milvus_ids=milvus_ids,
                doc_ids=doc_ids,
                chunk_ids=chunk_ids,
                embeddings=embeddings,
                chunk_types=chunk_types,
            )
        except MilvusError as exc:
            # Milvus 写入失败时，回滚 PostgreSQL 分块记录
            await chunk_repo.delete_by_doc_id(doc_id)
            raise RuntimeError(f"Milvus insert failed for doc {doc_id}: {exc}") from exc

        # 8. 更新 kb_chunks 的 milvus_id
        for kb_chunk in kb_chunks:
            kb_chunk_id: UUID = kb_chunk.id  # type: ignore[assignment]
            await chunk_repo.update_milvus_id(
                chunk_id=kb_chunk_id,
                milvus_id=str(kb_chunk_id),
                embedding_model=settings.embedding_model,
            )

        # 9. 更新 kb_documents 的 Milvus 同步状态
        await kb_repo.update_milvus_sync_status(doc_id, milvus_synced=True)

        # 10. 同步写入 Elasticsearch（IK 全文索引）
        es_sync_ok = await sync_document_to_es(doc_id)
        if not es_sync_ok:
            logger.warning(
                "ES index sync failed, will be compensated by scheduled task",
                extra={"doc_id": doc_id},
            )

        # 11. 更新 ai_tasks 状态为 SUCCESS
        if task is not None:
            await task_repo.update_status(
                cast(UUID, task.id),
                task_status="SUCCESS",
                result_payload={
                    "doc_id": doc_id,
                    "chunk_count": len(chunks),
                    "embedding_model": settings.embedding_model,
                    "embedding_dim": settings.embedding_dim,
                },
            )

        await session.commit()

        logger.info(
            "Document vectorization completed",
            extra={
                "doc_id": doc_id,
                "celery_task_id": celery_task_id,
                "chunk_count": len(chunks),
                "text_chunks": sum(1 for c in chunks if c.chunk_type == "TEXT"),
                "table_chunks": sum(1 for c in chunks if c.chunk_type == "TABLE"),
                "embedding_model": settings.embedding_model,
            },
        )

        return {
            "doc_id": doc_id,
            "status": "SUCCESS",
            "chunk_count": len(chunks),
            "embedding_model": settings.embedding_model,
        }


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    max_retries=3,
    default_retry_delay=15,
    soft_time_limit=600,
    time_limit=900,
)
def vectorize_document_task(self: Any, doc_id: str) -> dict[str, Any]:
    """
    文档分块与向量化 Celery 任务

    流程：
    1. 查询 kb_documents 获取解析结果路径
    2. 从 MinIO 下载结构化片段 JSON
    3. 分块（512 tokens/块，overlap 50，表格整体保留）
    4. 批量 Embedding（外部 API）
    5. 写入 PostgreSQL kb_chunks
    6. 写入 Milvus 向量库
    7. 更新 milvus_id 和同步状态

    失败时自动重试 3 次。
    """
    logger.info(
        "Document vectorization task started",
        extra={"doc_id": doc_id, "celery_task_id": self.request.id},
    )

    try:
        result = asyncio.run(_vectorize_document(doc_id, self.request.id))
        return result

    except Exception as exc:
        error_msg = str(exc)
        logger.error(
            "Document vectorization task failed",
            extra={"doc_id": doc_id, "error": error_msg},
            exc_info=True,
        )

        # 更新数据库状态为 FAILED
        try:
            asyncio.run(_mark_vectorize_task_failed(doc_id, self.request.id, error_msg))
        except Exception as mark_exc:
            logger.critical(
                "Failed to mark vectorize task as failed",
                extra={"doc_id": doc_id, "error": str(mark_exc)},
                exc_info=True,
            )

        # Celery 重试
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.critical(
                "Document vectorization task max retries exceeded",
                extra={"doc_id": doc_id, "error": error_msg},
            )
            self.update_state(state=states.FAILURE, meta={"error": error_msg})
            raise
