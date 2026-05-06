# ============================================================
# 单元测试：Celery OCR 任务
# ============================================================

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.ai.parsers.factory import UnsupportedFileTypeError
from app.ai.tasks import _mark_task_failed, _process_document
from app.models.kb_document import KbDocument


@pytest.fixture
def mock_doc() -> KbDocument:
    """Mock 文档对象"""
    doc = MagicMock(spec=KbDocument)
    doc.id = uuid4()
    doc.file_name = "test.pdf"
    doc.file_path = "2026/05/doc123/doc123.pdf"
    doc.mime_type = "application/pdf"
    return doc


class TestProcessDocument:
    """文档解析任务核心逻辑测试"""

    @patch("app.ai.tasks.MinioClient")
    @patch("app.ai.tasks.AsyncSessionLocal")
    @patch("app.ai.tasks.get_parser")
    async def test_success_flow(
        self,
        mock_get_parser: MagicMock,
        mock_session_cls: MagicMock,
        mock_minio_cls: MagicMock,
        mock_doc: MagicMock,
    ) -> None:
        """测试正常解析成功流程"""
        # Mock MinIO
        mock_minio = MagicMock()
        mock_minio_cls.return_value = mock_minio

        # Mock 解析器
        mock_parser = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "解析后的文本内容"
        mock_result.page_count = 5
        mock_result.word_count = 1000
        mock_result.is_scanned = False
        mock_parser.parse.return_value = mock_result
        mock_get_parser.return_value = mock_parser

        # Mock 数据库 Repository
        mock_kb_repo = MagicMock()
        mock_kb_repo.get_by_id = AsyncMock(return_value=mock_doc)
        mock_kb_repo.update_parse_status = AsyncMock()

        mock_task = MagicMock()
        mock_task.id = uuid4()
        mock_task_repo = MagicMock()
        mock_task_repo.get_by_ref = AsyncMock(return_value=mock_task)
        mock_task_repo.update_status = AsyncMock()

        # 注入 mock repo
        with patch("app.ai.tasks.KnowledgeRepository", return_value=mock_kb_repo):
            with patch("app.ai.tasks.AiTaskRepository", return_value=mock_task_repo):
                result = await _process_document("doc-123", "celery-task-456")

        assert result["status"] == "SUCCESS"
        assert result["page_count"] == 5
        assert result["word_count"] == 1000
        assert result["is_scanned"] is False
        assert result["parsed_text_path"] == "2026/05/doc123/doc123_parsed.txt"

        # 验证 MinIO 操作
        mock_minio.download_file.assert_called_once()
        mock_minio.upload_text.assert_called_once_with(
            "解析后的文本内容",
            "2026/05/doc123/doc123_parsed.txt",
        )

        # 验证数据库更新
        mock_kb_repo.update_parse_status.assert_called_once()
        call_kwargs = mock_kb_repo.update_parse_status.call_args.kwargs
        assert call_kwargs["parse_status"] == "SUCCESS"
        assert call_kwargs["page_count"] == 5
        assert call_kwargs["word_count"] == 1000
        assert call_kwargs["parsed_text_path"] == "2026/05/doc123/doc123_parsed.txt"

        mock_task_repo.update_status.assert_called()

    @patch("app.ai.tasks.MinioClient")
    @patch("app.ai.tasks.AsyncSessionLocal")
    @patch("app.ai.tasks.get_parser")
    async def test_document_not_found(
        self,
        mock_get_parser: MagicMock,
        mock_session_cls: MagicMock,
        mock_minio_cls: MagicMock,
        mock_doc: MagicMock,
    ) -> None:
        """测试文档不存在时抛出异常"""
        mock_kb_repo = MagicMock()
        mock_kb_repo.get_by_id = AsyncMock(return_value=None)

        with patch("app.ai.tasks.KnowledgeRepository", return_value=mock_kb_repo):
            with pytest.raises(ValueError, match="Document not found"):
                await _process_document("non-existent-doc", "celery-task-456")

    @patch("app.ai.tasks.MinioClient")
    @patch("app.ai.tasks.AsyncSessionLocal")
    @patch("app.ai.tasks.get_parser")
    async def test_no_associated_task(
        self,
        mock_get_parser: MagicMock,
        mock_session_cls: MagicMock,
        mock_minio_cls: MagicMock,
        mock_doc: MagicMock,
    ) -> None:
        """测试没有关联 ai_task 时的处理"""
        mock_minio = MagicMock()
        mock_minio_cls.return_value = mock_minio

        mock_parser = MagicMock()
        mock_result = MagicMock()
        mock_result.text = "文本"
        mock_result.page_count = 1
        mock_result.word_count = 10
        mock_result.is_scanned = False
        mock_parser.parse.return_value = mock_result
        mock_get_parser.return_value = mock_parser

        mock_kb_repo = MagicMock()
        mock_kb_repo.get_by_id = AsyncMock(return_value=mock_doc)
        mock_kb_repo.update_parse_status = AsyncMock()

        mock_task_repo = MagicMock()
        mock_task_repo.get_by_ref = AsyncMock(return_value=None)
        mock_task_repo.update_status = AsyncMock()

        with patch("app.ai.tasks.KnowledgeRepository", return_value=mock_kb_repo):
            with patch("app.ai.tasks.AiTaskRepository", return_value=mock_task_repo):
                result = await _process_document("doc-123", "celery-task-456")

        assert result["status"] == "SUCCESS"
        # 没有关联任务时，不应调用 update_status
        mock_task_repo.update_status.assert_not_called()

    @patch("app.ai.tasks.MinioClient")
    @patch("app.ai.tasks.AsyncSessionLocal")
    async def test_unsupported_file_type(
        self,
        mock_session_cls: MagicMock,
        mock_minio_cls: MagicMock,
        mock_doc: MagicMock,
    ) -> None:
        """测试不支持的文件类型"""
        mock_minio = MagicMock()
        mock_minio_cls.return_value = mock_minio

        mock_doc.mime_type = "application/zip"
        mock_kb_repo = MagicMock()
        mock_kb_repo.get_by_id = AsyncMock(return_value=mock_doc)

        mock_task_repo = MagicMock()
        mock_task_repo.get_by_ref = AsyncMock(return_value=None)

        with patch("app.ai.tasks.KnowledgeRepository", return_value=mock_kb_repo):
            with patch("app.ai.tasks.AiTaskRepository", return_value=mock_task_repo):
                with pytest.raises(UnsupportedFileTypeError):
                    await _process_document(str(uuid4()), "celery-task-456")


class TestMarkTaskFailed:
    """任务失败标记测试"""

    @patch("app.ai.tasks.AsyncSessionLocal")
    async def test_mark_failed(self, mock_session_cls: MagicMock) -> None:
        """测试标记任务失败"""
        mock_kb_repo = MagicMock()
        mock_kb_repo.update_parse_status = AsyncMock()

        mock_task = MagicMock()
        mock_task.id = uuid4()
        mock_task_repo = MagicMock()
        mock_task_repo.get_by_ref = AsyncMock(return_value=mock_task)
        mock_task_repo.update_status = AsyncMock()

        with patch("app.ai.tasks.KnowledgeRepository", return_value=mock_kb_repo):
            with patch("app.ai.tasks.AiTaskRepository", return_value=mock_task_repo):
                await _mark_task_failed("doc-123", "解析失败")

        mock_kb_repo.update_parse_status.assert_called_once_with(
            "doc-123",
            parse_status="FAILED",
            parse_error="解析失败",
        )
        mock_task_repo.update_status.assert_called_once_with(
            mock_task.id,
            task_status="FAILED",
            error_message="解析失败",
        )
