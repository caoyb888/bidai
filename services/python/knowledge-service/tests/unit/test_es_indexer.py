# ============================================================
# 单元测试：ES 索引同步封装（es_indexer）
# ============================================================

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.ai.es_client import ESClient
from app.ai.es_indexer import sync_document_to_es
from app.models.kb_chunk import KbChunk
from app.models.kb_document import KbDocument


@pytest.fixture(autouse=True)
def reset_singletons() -> None:
    """每次测试前重置 ESClient 单例"""
    ESClient._instance = None
    ESClient._client = None
    yield
    ESClient._instance = None
    ESClient._client = None


class TestSyncDocumentToEs:
    """sync_document_to_es 单元测试"""

    @patch("app.ai.es_indexer.ESClient")
    @patch("app.ai.es_indexer.AsyncSessionLocal")
    async def test_sync_success(
        self,
        mock_session_cls: MagicMock,
        mock_es_cls: MagicMock,
    ) -> None:
        """测试正常同步成功流程"""
        doc = MagicMock(spec=KbDocument)
        doc.id = uuid4()
        doc.title = "测试文档"
        doc.tags = ["tag1", "tag2"]
        doc.deleted_at = None

        chunk = MagicMock(spec=KbChunk)
        chunk.id = uuid4()
        chunk.content = "chunk内容"
        chunk.chunk_type = "TEXT"
        chunk.page_no = 1
        chunk.section_title = "章节标题"

        mock_kb_repo = MagicMock()
        mock_kb_repo.get_by_id = AsyncMock(return_value=doc)
        mock_kb_repo.update_es_index_status = AsyncMock()

        mock_chunk_repo = MagicMock()
        mock_chunk_repo.get_by_doc_id = AsyncMock(return_value=[chunk])

        mock_session = MagicMock()
        mock_session.commit = AsyncMock()
        mock_session_cls.return_value = MagicMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=None),
        )

        mock_es = MagicMock()
        mock_es.ensure_index = AsyncMock()
        mock_es.bulk_index_chunks = AsyncMock()
        mock_es_cls.return_value = mock_es

        with patch(
            "app.ai.es_indexer.KnowledgeRepository", return_value=mock_kb_repo
        ):
            with patch(
                "app.ai.es_indexer.KbChunkRepository", return_value=mock_chunk_repo
            ):
                result = await sync_document_to_es(str(doc.id))

        assert result is True
        mock_es.ensure_index.assert_awaited_once()
        mock_es.bulk_index_chunks.assert_awaited_once()
        call_args = mock_es.bulk_index_chunks.call_args.args[0]
        assert len(call_args) == 1
        assert call_args[0]["chunk_id"] == str(chunk.id)
        assert call_args[0]["doc_title"] == doc.title
        assert call_args[0]["tags"] == ["tag1", "tag2"]
        mock_kb_repo.update_es_index_status.assert_awaited_once_with(
            str(doc.id), es_indexed=True
        )
        mock_session.commit.assert_awaited_once()

    @patch("app.ai.es_indexer.AsyncSessionLocal")
    async def test_sync_doc_not_found(
        self,
        mock_session_cls: MagicMock,
    ) -> None:
        """测试文档不存在时返回 False"""
        mock_kb_repo = MagicMock()
        mock_kb_repo.get_by_id = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session_cls.return_value = MagicMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=None),
        )

        with patch(
            "app.ai.es_indexer.KnowledgeRepository", return_value=mock_kb_repo
        ):
            result = await sync_document_to_es("missing-doc-id")

        assert result is False

    @patch("app.ai.es_indexer.AsyncSessionLocal")
    async def test_sync_doc_soft_deleted(
        self,
        mock_session_cls: MagicMock,
    ) -> None:
        """测试文档已软删除时返回 False"""
        doc = MagicMock(spec=KbDocument)
        doc.deleted_at = "2024-01-01T00:00:00Z"

        mock_kb_repo = MagicMock()
        mock_kb_repo.get_by_id = AsyncMock(return_value=doc)

        mock_session = MagicMock()
        mock_session_cls.return_value = MagicMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=None),
        )

        with patch(
            "app.ai.es_indexer.KnowledgeRepository", return_value=mock_kb_repo
        ):
            result = await sync_document_to_es("deleted-doc-id")

        assert result is False

    @patch("app.ai.es_indexer.AsyncSessionLocal")
    async def test_sync_no_chunks(
        self,
        mock_session_cls: MagicMock,
    ) -> None:
        """测试文档无分块时返回 False"""
        doc = MagicMock(spec=KbDocument)
        doc.deleted_at = None

        mock_kb_repo = MagicMock()
        mock_kb_repo.get_by_id = AsyncMock(return_value=doc)

        mock_chunk_repo = MagicMock()
        mock_chunk_repo.get_by_doc_id = AsyncMock(return_value=[])

        mock_session = MagicMock()
        mock_session_cls.return_value = MagicMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=None),
        )

        with patch(
            "app.ai.es_indexer.KnowledgeRepository", return_value=mock_kb_repo
        ):
            with patch(
                "app.ai.es_indexer.KbChunkRepository", return_value=mock_chunk_repo
            ):
                result = await sync_document_to_es("doc-id")

        assert result is False

    @patch("app.ai.es_indexer.ESClient")
    @patch("app.ai.es_indexer.AsyncSessionLocal")
    async def test_sync_es_bulk_failure(
        self,
        mock_session_cls: MagicMock,
        mock_es_cls: MagicMock,
    ) -> None:
        """测试 ES bulk 失败时返回 False"""
        from app.ai.es_client import ESError

        doc = MagicMock(spec=KbDocument)
        doc.title = "测试"
        doc.tags = []
        doc.deleted_at = None

        chunk = MagicMock(spec=KbChunk)
        chunk.id = uuid4()
        chunk.content = "内容"
        chunk.chunk_type = "TEXT"
        chunk.page_no = None
        chunk.section_title = None

        mock_kb_repo = MagicMock()
        mock_kb_repo.get_by_id = AsyncMock(return_value=doc)

        mock_chunk_repo = MagicMock()
        mock_chunk_repo.get_by_doc_id = AsyncMock(return_value=[chunk])

        mock_session = MagicMock()
        mock_session_cls.return_value = MagicMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(return_value=None),
        )

        mock_es = MagicMock()
        mock_es.ensure_index = AsyncMock()
        mock_es.bulk_index_chunks = AsyncMock(side_effect=ESError("ES cluster down"))
        mock_es_cls.return_value = mock_es

        with patch(
            "app.ai.es_indexer.KnowledgeRepository", return_value=mock_kb_repo
        ):
            with patch(
                "app.ai.es_indexer.KbChunkRepository", return_value=mock_chunk_repo
            ):
                result = await sync_document_to_es("doc-id")

        assert result is False
        mock_es.ensure_index.assert_awaited_once()
        mock_es.bulk_index_chunks.assert_awaited_once()
