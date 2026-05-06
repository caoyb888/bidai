# ============================================================
# 知识库数据访问层 — Repository
# ============================================================


from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kb_document import KbDocument


class KnowledgeRepository:
    """知识库文档 Repository"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_file_hash(self, file_hash: str) -> KbDocument | None:
        """根据 SHA-256 哈希查询文档（软删除过滤）"""
        stmt = select(KbDocument).where(
            KbDocument.file_hash == file_hash,
            KbDocument.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id(self, doc_id: str) -> KbDocument | None:
        """根据 ID 查询文档（软删除过滤）"""
        from uuid import UUID

        stmt = select(KbDocument).where(
            KbDocument.id == UUID(doc_id),
            KbDocument.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, doc: KbDocument) -> KbDocument:
        """创建文档记录"""
        self.session.add(doc)
        await self.session.flush()
        await self.session.refresh(doc)
        return doc

    async def update_parse_status(
        self,
        doc_id: str,
        *,
        parse_status: str,
        page_count: int | None = None,
        word_count: int | None = None,
        parsed_text_path: str | None = None,
        parse_error: str | None = None,
    ) -> None:
        """更新文档解析状态"""
        from datetime import UTC, datetime
        from uuid import UUID

        doc = await self.session.get(KbDocument, UUID(doc_id))
        if doc is None:
            return
        doc.parse_status = parse_status  # type: ignore[assignment]
        doc.parsed_at = datetime.now(UTC)  # type: ignore[assignment]
        if page_count is not None:
            doc.page_count = page_count  # type: ignore[assignment]
        if word_count is not None:
            doc.word_count = word_count  # type: ignore[assignment]
        if parsed_text_path is not None:
            doc.parsed_text_path = parsed_text_path  # type: ignore[assignment]
        if parse_error is not None:
            doc.parse_error = parse_error  # type: ignore[assignment]
        await self.session.flush()
