# ============================================================
# 单元测试：KnowledgeService 文档列表/详情/删除
# ============================================================

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.models.kb_document import KbDocument
from app.schemas.base import KnowledgeDocument
from app.services.knowledge import KnowledgeService


@pytest.fixture
def mock_session() -> MagicMock:
    """Mock AsyncSession"""
    session = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def service(mock_session: MagicMock) -> KnowledgeService:
    svc = KnowledgeService(mock_session)
    svc.kb_repo = MagicMock()
    svc.chunk_repo = MagicMock()
    return svc


def _make_kb_document(**kwargs: object) -> KbDocument:
    """构造 KbDocument ORM 对象"""
    doc = KbDocument()
    doc.id = kwargs.get("id", uuid4())
    doc.title = kwargs.get("title", "测试文档")
    doc.doc_type = kwargs.get("doc_type", "MISC")
    doc.file_name = kwargs.get("file_name", "test.pdf")
    doc.tags = kwargs.get("tags", [])
    doc.page_count = kwargs.get("page_count", 10)
    doc.confidence = kwargs.get("confidence", 0.0)
    doc.ingest_mode = kwargs.get("ingest_mode", "AUTO")
    doc.is_expired = kwargs.get("is_expired", False)
    doc.created_at = kwargs.get("created_at", datetime.now(UTC))
    return doc


class TestListDocuments:
    """KnowledgeService.list_documents 测试"""

    @pytest.mark.asyncio
    async def test_list_basic(self, service: KnowledgeService) -> None:
        """测试基础列表查询"""
        doc = _make_kb_document(title="文档A", doc_type="QUALIFICATION")
        service.kb_repo.count_documents = AsyncMock(return_value=1)
        service.kb_repo.list_documents = AsyncMock(return_value=[doc])

        result = await service.list_documents(
            page=1, page_size=20, doc_category=None, tags=None, is_expired=None, keyword=None
        )

        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].title == "文档A"
        assert result.total_pages == 1

    @pytest.mark.asyncio
    async def test_list_with_category_filter(self, service: KnowledgeService) -> None:
        """测试按分类筛选"""
        service.kb_repo.count_documents = AsyncMock(return_value=0)
        service.kb_repo.list_documents = AsyncMock(return_value=[])

        await service.list_documents(
            page=1, page_size=20, doc_category="SOLUTION_TEMPLATE", tags=None, is_expired=None, keyword=None
        )

        call_kwargs = service.kb_repo.list_documents.call_args.kwargs
        assert call_kwargs["doc_type"] == "SOLUTION"

    @pytest.mark.asyncio
    async def test_list_pagination(self, service: KnowledgeService) -> None:
        """测试分页计算"""
        service.kb_repo.count_documents = AsyncMock(return_value=45)
        service.kb_repo.list_documents = AsyncMock(return_value=[])

        result = await service.list_documents(
            page=2, page_size=20, doc_category=None, tags=None, is_expired=None, keyword=None
        )

        assert result.page == 2
        assert result.page_size == 20
        assert result.total_pages == 3


class TestGetDocument:
    """KnowledgeService.get_document 测试"""

    @pytest.mark.asyncio
    async def test_get_success(self, service: KnowledgeService) -> None:
        """测试正常获取详情"""
        doc = _make_kb_document(title="详情文档", doc_type="PERFORMANCE")
        service.kb_repo.get_by_id = AsyncMock(return_value=doc)

        result = await service.get_document(str(doc.id))

        assert isinstance(result, KnowledgeDocument)
        assert result.title == "详情文档"
        assert result.doc_category == "PERFORMANCE"

    @pytest.mark.asyncio
    async def test_get_not_found(self, service: KnowledgeService) -> None:
        """测试文档不存在抛出 NotFoundError"""
        service.kb_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError) as exc_info:
            await service.get_document("non-existent")

        assert exc_info.value.biz_code == 40002


class TestDeleteDocument:
    """KnowledgeService.delete_document 测试"""

    @pytest.mark.asyncio
    async def test_delete_success(self, service: KnowledgeService) -> None:
        """测试正常删除流程"""
        doc = _make_kb_document()
        service.kb_repo.get_by_id = AsyncMock(return_value=doc)
        service.kb_repo.soft_delete = AsyncMock(return_value=doc)
        service.chunk_repo.delete_by_doc_id = AsyncMock(return_value=5)

        with patch("app.services.knowledge.MilvusClient") as mock_milvus_cls, \
             patch("app.services.knowledge.ESClient") as mock_es_cls:
            mock_milvus_cls.return_value.delete_by_doc_id = MagicMock()
            mock_es_inst = MagicMock()
            mock_es_inst.delete_by_doc_id = AsyncMock()
            mock_es_cls.return_value = mock_es_inst

            await service.delete_document(str(doc.id), "user_001")

        service.kb_repo.soft_delete.assert_called_once_with(str(doc.id), "user_001")
        service.chunk_repo.delete_by_doc_id.assert_called_once_with(str(doc.id))
        service.session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, service: KnowledgeService) -> None:
        """测试删除不存在的文档抛出 NotFoundError"""
        service.kb_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError) as exc_info:
            await service.delete_document("non-existent", "user_001")

        assert exc_info.value.biz_code == 40002

    @pytest.mark.asyncio
    async def test_delete_milvus_failure_ignored(self, service: KnowledgeService) -> None:
        """测试 Milvus 删除失败不影响整体删除结果"""
        doc = _make_kb_document()
        service.kb_repo.get_by_id = AsyncMock(return_value=doc)
        service.kb_repo.soft_delete = AsyncMock(return_value=doc)
        service.chunk_repo.delete_by_doc_id = AsyncMock(return_value=3)

        with patch("app.services.knowledge.MilvusClient") as mock_milvus_cls, \
             patch("app.services.knowledge.ESClient") as mock_es_cls:
            mock_milvus_cls.return_value.delete_by_doc_id = MagicMock(
                side_effect=Exception("milvus down")
            )
            mock_es_inst = MagicMock()
            mock_es_inst.delete_by_doc_id = AsyncMock()
            mock_es_cls.return_value = mock_es_inst

            # 不应抛出异常
            await service.delete_document(str(doc.id), "user_001")

        mock_milvus_cls.return_value.delete_by_doc_id.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_es_failure_ignored(self, service: KnowledgeService) -> None:
        """测试 ES 删除失败不影响整体删除结果"""
        doc = _make_kb_document()
        service.kb_repo.get_by_id = AsyncMock(return_value=doc)
        service.kb_repo.soft_delete = AsyncMock(return_value=doc)
        service.chunk_repo.delete_by_doc_id = AsyncMock(return_value=3)

        with patch("app.services.knowledge.MilvusClient") as mock_milvus_cls, \
             patch("app.services.knowledge.ESClient") as mock_es_cls:
            mock_milvus_cls.return_value.delete_by_doc_id = MagicMock()
            mock_es_inst = MagicMock()
            mock_es_inst.delete_by_doc_id = AsyncMock(side_effect=Exception("es down"))
            mock_es_cls.return_value = mock_es_inst

            # 不应抛出异常
            await service.delete_document(str(doc.id), "user_001")

        mock_es_inst.delete_by_doc_id.assert_called_once()
