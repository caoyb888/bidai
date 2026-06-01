# ============================================================
# 知识库数据访问层 — Repository
# ============================================================

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import array as pg_array
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

    def _build_list_filters(
        self,
        doc_type: str | None = None,
        tags: list[str] | None = None,
        is_expired: bool | None = None,
        keyword: str | None = None,
    ) -> list[Any]:
        """构建列表查询的过滤条件"""
        filters: list[Any] = [KbDocument.deleted_at.is_(None)]
        if doc_type:
            filters.append(KbDocument.doc_type == doc_type)
        if tags:
            filters.append(KbDocument.tags.overlap(pg_array(tags)))
        if is_expired is not None:
            filters.append(KbDocument.is_expired == is_expired)
        if keyword:
            filters.append(KbDocument.title.ilike(f"%{keyword}%"))
        return filters

    async def list_documents(
        self,
        *,
        doc_type: str | None = None,
        tags: list[str] | None = None,
        is_expired: bool | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[KbDocument]:
        """查询文档列表（支持分页和筛选）"""
        filters = self._build_list_filters(doc_type, tags, is_expired, keyword)
        stmt = (
            select(KbDocument)
            .where(*filters)
            .order_by(KbDocument.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_documents(
        self,
        *,
        doc_type: str | None = None,
        tags: list[str] | None = None,
        is_expired: bool | None = None,
        keyword: str | None = None,
    ) -> int:
        """统计文档数量"""
        filters = self._build_list_filters(doc_type, tags, is_expired, keyword)
        stmt = select(func.count(KbDocument.id)).where(*filters)
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def soft_delete(self, doc_id: str, user_id: str) -> KbDocument | None:
        """软删除文档"""
        doc = await self.get_by_id(doc_id)
        if doc is None:
            return None
        doc.deleted_at = datetime.now(UTC)  # type: ignore[assignment]
        doc.updated_by = user_id  # type: ignore[assignment]
        await self.session.flush()
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

    async def update_milvus_sync_status(
        self,
        doc_id: str,
        *,
        milvus_synced: bool,
    ) -> None:
        """更新文档 Milvus 同步状态"""
        doc = await self.session.get(KbDocument, UUID(doc_id))
        if doc is None:
            return
        doc.milvus_synced = milvus_synced  # type: ignore[assignment]
        doc.milvus_synced_at = datetime.now(UTC)  # type: ignore[assignment]
        await self.session.flush()

    async def update_es_index_status(
        self,
        doc_id: str,
        *,
        es_indexed: bool,
    ) -> None:
        """更新文档 ES 索引同步状态"""
        doc = await self.session.get(KbDocument, UUID(doc_id))
        if doc is None:
            return
        doc.es_indexed = es_indexed  # type: ignore[assignment]
        doc.es_indexed_at = datetime.now(UTC)  # type: ignore[assignment]
        await self.session.flush()

    # ------------------------------------------------------------------
    # 统计查询（S1-2-006）
    # ------------------------------------------------------------------

    async def get_category_counts(self) -> dict[str, dict[str, int]]:
        """按 doc_type 统计各分类文档数量及过期数量"""
        stmt = (
            select(
                KbDocument.doc_type,
                func.count(KbDocument.id).label("total"),
                func.count(KbDocument.id)
                .filter(KbDocument.is_expired.is_(True))
                .label("expired"),
            )
            .where(KbDocument.deleted_at.is_(None))
            .group_by(KbDocument.doc_type)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return {
            str(row.doc_type): {"total": int(row.total), "expired": int(row.expired)}
            for row in rows
        }

    async def get_expired_ratio(self) -> float:
        """计算有 expire_date 的文档中已过期的比例（0~1）"""
        stmt = select(
            func.count(KbDocument.id).filter(KbDocument.is_expired.is_(True)).label("expired"),
            func.count(KbDocument.id).label("total"),
        ).where(
            KbDocument.deleted_at.is_(None),
            KbDocument.expire_date.is_not(None),
        )
        result = await self.session.execute(stmt)
        row = result.one()
        total = row.total or 0
        if total == 0:
            return 0.0
        return float(row.expired or 0) / float(total)

    async def get_recent_30d_count(self) -> int:
        """近30天新增文档数"""
        since = datetime.now(UTC) - timedelta(days=30)
        stmt = select(func.count(KbDocument.id)).where(
            KbDocument.deleted_at.is_(None),
            KbDocument.created_at >= since,
        )
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_expiring_soon(self, days: int = 30) -> list[KbDocument]:
        """获取即将过期的文档（未过期且 expire_date 在指定天数内）"""
        threshold = date.today() + timedelta(days=days)
        stmt = (
            select(KbDocument)
            .where(
                KbDocument.deleted_at.is_(None),
                KbDocument.expire_date.is_not(None),
                KbDocument.is_expired.is_(False),
                KbDocument.expire_date <= threshold,
            )
            .order_by(KbDocument.expire_date.asc())
            .limit(50)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_unindexed_documents(
        self,
        *,
        limit: int = 50,
    ) -> list[KbDocument]:
        """查询已解析完成但尚未同步 ES 的文档（用于补偿任务）"""
        stmt = (
            select(KbDocument)
            .where(
                KbDocument.deleted_at.is_(None),
                KbDocument.parse_status == "SUCCESS",
                KbDocument.es_indexed.is_(False),
            )
            .order_by(KbDocument.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
