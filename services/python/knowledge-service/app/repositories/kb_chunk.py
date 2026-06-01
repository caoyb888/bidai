# ============================================================
# KbChunk 数据访问层 — Repository
# ============================================================

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_chunk import KbChunk


class KbChunkRepository:
    """文档分块 Repository"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, chunk: KbChunk) -> KbChunk:
        """创建分块记录"""
        self.session.add(chunk)
        await self.session.flush()
        await self.session.refresh(chunk)
        return chunk

    async def create_many(self, chunks: list[KbChunk]) -> list[KbChunk]:
        """批量创建分块记录"""
        self.session.add_all(chunks)
        await self.session.flush()
        for chunk in chunks:
            await self.session.refresh(chunk)
        return chunks

    async def get_by_doc_id(self, doc_id: str) -> list[KbChunk]:
        """根据文档 ID 查询所有分块"""
        stmt = select(KbChunk).where(KbChunk.doc_id == UUID(doc_id)).order_by(KbChunk.chunk_index)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_doc_id(self, doc_id: str) -> int:
        """根据文档 ID 删除所有分块，返回删除数量"""
        stmt = delete(KbChunk).where(KbChunk.doc_id == UUID(doc_id))
        result = await self.session.execute(stmt)
        return getattr(result, "rowcount", 0) or 0

    async def update_milvus_id(
        self,
        chunk_id: UUID,
        milvus_id: str,
        embedding_model: str,
    ) -> None:
        """更新分块的 Milvus 引用信息"""
        from datetime import UTC, datetime

        chunk = await self.session.get(KbChunk, chunk_id)
        if chunk is None:
            return
        chunk.milvus_id = milvus_id  # type: ignore[assignment]
        chunk.embedding_model = embedding_model  # type: ignore[assignment]
        chunk.embedded_at = datetime.now(UTC)  # type: ignore[assignment]
        await self.session.flush()

    async def get_by_chunk_ids(self, chunk_ids: list[str]) -> list[KbChunk]:
        """根据 chunk_id 列表批量查询分块"""
        from uuid import UUID

        if not chunk_ids:
            return []

        ids = [UUID(cid) for cid in chunk_ids]
        stmt = select(KbChunk).where(KbChunk.id.in_(ids))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
