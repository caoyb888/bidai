# ============================================================
# 单元测试：向量化 Celery 任务
# ============================================================

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.ai.es_client import ESClient
from app.ai.vectorize_tasks import _vectorize_document
from app.models.kb_document import KbDocument

DOC_ID = str(uuid4())


@pytest.fixture(autouse=True)
def reset_singletons() -> None:
    """重置单例实例，避免 event loop 污染"""
    ESClient._instance = None
    ESClient._client = None
    yield
    ESClient._instance = None
    ESClient._client = None


@pytest.fixture
def mock_doc() -> KbDocument:
    """Mock 文档对象"""
    doc = MagicMock(spec=KbDocument)
    doc.id = uuid4()
    doc.file_path = "2026/05/doc456/doc456.pdf"
    doc.parse_status = "SUCCESS"
    return doc


class TestVectorizeDocument:
    """向量化任务核心逻辑测试"""

    @patch("app.ai.vectorize_tasks.sync_document_to_es")
    @patch("app.ai.vectorize_tasks.MinioClient")
    @patch("app.ai.vectorize_tasks.DocumentChunker")
    @patch("app.ai.vectorize_tasks.EmbeddingClient")
    @patch("app.ai.vectorize_tasks.MilvusClient")
    @patch("app.ai.vectorize_tasks.AsyncSessionLocal")
    async def test_success_flow(
        self,
        mock_session_cls: MagicMock,
        mock_milvus_cls: MagicMock,
        mock_embed_cls: MagicMock,
        mock_chunker_cls: MagicMock,
        mock_minio_cls: MagicMock,
        mock_sync_es: AsyncMock,
        mock_doc: MagicMock,
    ) -> None:
        """测试正常向量化成功流程"""
        # Mock MinIO
        mock_minio = MagicMock()
        fragments_data = [
            {"content": "段落文本", "page_no": 1, "fragment_type": "TEXT", "section_title": ""},
            {"content": "A | B\n1 | 2", "page_no": 1, "fragment_type": "TABLE", "section_title": ""},
        ]
        mock_minio.download_text.return_value = json.dumps(fragments_data)
        mock_minio_cls.return_value = mock_minio

        # Mock 分块器
        from app.ai.chunker import Chunk

        mock_chunks = [
            Chunk(content="段落文本", chunk_type="TEXT", token_count=10, char_count=4, page_no=None),
            Chunk(content="A | B\n1 | 2", chunk_type="TABLE", token_count=8, char_count=10, page_no=1),
        ]
        mock_chunker = MagicMock()
        mock_chunker.chunk_fragments.return_value = mock_chunks
        mock_chunker_cls.return_value = mock_chunker

        # Mock Embedding
        mock_embed_client = MagicMock()
        mock_embed_client.embed = AsyncMock(return_value=[[0.1] * 1536, [0.2] * 1536])
        mock_embed_cls.return_value = mock_embed_client

        # Mock Milvus
        mock_milvus = MagicMock()
        mock_milvus.insert_chunks = MagicMock()
        mock_milvus_cls.return_value = mock_milvus

        # Mock 数据库 Repository
        mock_kb_repo = MagicMock()
        mock_kb_repo.get_by_id = AsyncMock(return_value=mock_doc)
        mock_kb_repo.update_milvus_sync_status = AsyncMock()

        mock_chunk_repo = MagicMock()
        mock_chunk_repo.delete_by_doc_id = AsyncMock(return_value=0)
        mock_chunk_repo.create_many = AsyncMock()
        mock_chunk_repo.update_milvus_id = AsyncMock()

        mock_task = MagicMock()
        mock_task.id = uuid4()
        mock_task_repo = MagicMock()
        mock_task_repo.get_by_ref = AsyncMock(return_value=mock_task)
        mock_task_repo.update_status = AsyncMock()

        with patch("app.ai.vectorize_tasks.KnowledgeRepository", return_value=mock_kb_repo):
            with patch("app.ai.vectorize_tasks.KbChunkRepository", return_value=mock_chunk_repo):
                with patch("app.ai.vectorize_tasks.AiTaskRepository", return_value=mock_task_repo):
                    result = await _vectorize_document(DOC_ID, "celery-task-789")

        assert result["status"] == "SUCCESS"
        assert result["chunk_count"] == 2

        # 验证 MinIO 下载了 fragments JSON
        mock_minio.download_text.assert_called_once_with("2026/05/doc456/doc456_fragments.json")

        # 验证 Embedding 被调用
        mock_embed_client.embed.assert_called_once_with(["段落文本", "A | B\n1 | 2"])

        # 验证 Milvus 插入
        mock_milvus.insert_chunks.assert_called_once()
        call_kwargs = mock_milvus.insert_chunks.call_args.kwargs
        assert len(call_kwargs["milvus_ids"]) == 2
        assert call_kwargs["chunk_types"] == ["TEXT", "TABLE"]

        # 验证数据库更新
        mock_kb_repo.update_milvus_sync_status.assert_called_once_with(DOC_ID, milvus_synced=True)
        mock_task_repo.update_status.assert_called()

    @patch("app.ai.vectorize_tasks.MinioClient")
    @patch("app.ai.vectorize_tasks.AsyncSessionLocal")
    async def test_document_not_found(
        self,
        mock_session_cls: MagicMock,
        mock_minio_cls: MagicMock,
    ) -> None:
        """测试文档不存在时抛出异常"""
        mock_kb_repo = MagicMock()
        mock_kb_repo.get_by_id = AsyncMock(return_value=None)

        with patch("app.ai.vectorize_tasks.KnowledgeRepository", return_value=mock_kb_repo):
            with pytest.raises(ValueError, match="Document not found"):
                await _vectorize_document(str(uuid4()), "celery-task-789")

    @patch("app.ai.vectorize_tasks.MinioClient")
    @patch("app.ai.vectorize_tasks.AsyncSessionLocal")
    async def test_document_not_parsed(
        self,
        mock_session_cls: MagicMock,
        mock_minio_cls: MagicMock,
        mock_doc: MagicMock,
    ) -> None:
        """测试文档未解析时抛出异常"""
        mock_doc.parse_status = "PENDING"
        mock_kb_repo = MagicMock()
        mock_kb_repo.get_by_id = AsyncMock(return_value=mock_doc)

        with patch("app.ai.vectorize_tasks.KnowledgeRepository", return_value=mock_kb_repo):
            with pytest.raises(ValueError, match="Document not parsed yet"):
                await _vectorize_document(DOC_ID, "celery-task-789")

    @patch("app.ai.vectorize_tasks.sync_document_to_es")
    @patch("app.ai.vectorize_tasks.MinioClient")
    @patch("app.ai.vectorize_tasks.DocumentChunker")
    @patch("app.ai.vectorize_tasks.EmbeddingClient")
    @patch("app.ai.vectorize_tasks.MilvusClient")
    @patch("app.ai.vectorize_tasks.AsyncSessionLocal")
    async def test_fallback_to_parsed_text(
        self,
        mock_session_cls: MagicMock,
        mock_milvus_cls: MagicMock,
        mock_embed_cls: MagicMock,
        mock_chunker_cls: MagicMock,
        mock_minio_cls: MagicMock,
        mock_sync_es: AsyncMock,
        mock_doc: MagicMock,
    ) -> None:
        """测试 fragments JSON 缺失时回退到解析文本"""
        mock_minio = MagicMock()
        # 第一次调用（fragments JSON）失败
        mock_minio.download_text.side_effect = [
            Exception("fragments not found"),
            "纯文本内容",
        ]
        mock_minio_cls.return_value = mock_minio

        from app.ai.chunker import Chunk

        mock_chunks = [Chunk(content="纯文本内容", chunk_type="TEXT", token_count=5, char_count=5)]
        mock_chunker = MagicMock()
        mock_chunker.chunk_fragments.return_value = mock_chunks
        mock_chunker_cls.return_value = mock_chunker

        mock_embed_client = MagicMock()
        mock_embed_client.embed = AsyncMock(return_value=[[0.1] * 1536])
        mock_embed_cls.return_value = mock_embed_client

        mock_milvus = MagicMock()
        mock_milvus.insert_chunks = MagicMock()
        mock_milvus_cls.return_value = mock_milvus

        mock_kb_repo = MagicMock()
        mock_kb_repo.get_by_id = AsyncMock(return_value=mock_doc)
        mock_kb_repo.update_milvus_sync_status = AsyncMock()

        mock_chunk_repo = MagicMock()
        mock_chunk_repo.delete_by_doc_id = AsyncMock(return_value=0)
        mock_chunk_repo.create_many = AsyncMock()
        mock_chunk_repo.update_milvus_id = AsyncMock()

        mock_task_repo = MagicMock()
        mock_task_repo.get_by_ref = AsyncMock(return_value=None)
        mock_task_repo.update_status = AsyncMock()

        with patch("app.ai.vectorize_tasks.KnowledgeRepository", return_value=mock_kb_repo):
            with patch("app.ai.vectorize_tasks.KbChunkRepository", return_value=mock_chunk_repo):
                with patch("app.ai.vectorize_tasks.AiTaskRepository", return_value=mock_task_repo):
                    result = await _vectorize_document(DOC_ID, "celery-task-789")

        assert result["status"] == "SUCCESS"
        assert result["chunk_count"] == 1
        # 验证回退时下载了 parsed text
        assert mock_minio.download_text.call_count == 2
        # 验证 ES 同步被调用（S1-2-007）
        mock_sync_es.assert_awaited_once_with(DOC_ID)
